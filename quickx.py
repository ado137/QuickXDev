#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: lonewolf
# Date: 2013-10-26 11:23:48
#
import sublime
import sublime_plugin
import functools
import os
import datetime
import json
import re
import subprocess
import sys
import time
import codecs
try:
	import helper
	import rebuild
	import definition
except ImportError:
	from . import helper
	from . import rebuild
	from . import definition

TEMP_PATH=""
DEFINITION_LIST=[]
USER_DEFINITION_LIST=[]
luaTemplate="""--
-- Author: ${author}
-- Date: ${date}
--
"""
compile_scripts_bat="""@echo off
set DIR=%~dp0
%DIR%win32\php.exe "%DIR%lib\compile_scripts.php" %*
"""

# init plugin,load definitions
def init():
	global TEMP_PATH
	TEMP_PATH=sublime.packages_path()+"/User/QuickXDev.cache"
	global DEFINITION_LIST
	DEFINITION_LIST=json.loads(definition.data)
	global USER_DEFINITION_LIST
	path=os.path.join(TEMP_PATH,"user_definition.json")
	if os.path.exists(path):
		USER_DEFINITION_LIST=json.loads(helper.readFile(path))

def checkRoot():
	# quick_cocos2dx_root
	settings = helper.loadSettings("QuickXDev")
	quick_cocos2dx_root = settings.get("quick_cocos2dx_root", "")
	if len(quick_cocos2dx_root)==0:
		sublime.error_message("quick_cocos2dx_root no set")
		return False
	return quick_cocos2dx_root


def getEnvironment():
	settings = helper.loadSettings("QuickXDev")

	keys = ["QUICK_COCOS2DX_ROOT", "ANDROID_NDK_ROOT", "COCOS2DX_ROOT"]
	env = dict()

	for key in keys:
		value = settings.get(key.lower(), "")
		if len(value)==0:
			sublime.error_message("{0} no set".format(key.lower()))
			return
		env[key] = value

	return env

def getProjectPath(dir):
	find_index = dir.find("scripts")
	
	if find_index == -1:
		sublime.error_message("The file '{}' not in sctipts path.".format(dir))
		return ""

	return dir[:find_index - 1]

def getAndroidPath(dir):
	proj_path = getProjectPath(dir)

	if proj_path == "":
		return ""

	return proj_path+"/proj.android"


def run_player_with_path(parent, quick_cocos2dx_root, script_path):
	# player path for platform
	playerPath=""
	if sublime.platform()=="osx":
		playerPath=quick_cocos2dx_root+"/player/mac/quick-x-player.app/Contents/MacOS/quick-x-player"
	elif sublime.platform()=="windows":
		playerPath=quick_cocos2dx_root+"/player/win/quick-x-player.exe"
	if playerPath=="" or not os.path.exists(playerPath):
		sublime.error_message("player no exists")
		return
	args=[playerPath]
	# param
	path=script_path
	args.append("-workdir")
	args.append(os.path.split(path)[0])
	args.append("-file")
	args.append("scripts/main.lua")
	args.append("-load-framework")
	configPath=path+"/config.lua"
	if os.path.exists(configPath):
		f=codecs.open(configPath,"r","utf-8")
		width=640
		height=960
		while True:
			line=f.readline()
			if line:
				# debug
				m=re.match("^DEBUG\s*=\s*(\d+)",line)
				if m:
					debug=m.group(1)
					if debug=="0":
						args.append("-disable-write-debug-log")
						args.append("-disable-console")
					elif debug=="1":
						args.append("-disable-write-debug-log")
						args.append("-console")
					else:
						args.append("-write-debug-log")
						args.append("-console")
				# resolution
				m=re.match("^CONFIG_SCREEN_WIDTH\s*=\s*(\d+)",line)
				if m:
					width=m.group(1)
				m=re.match("^CONFIG_SCREEN_HEIGHT\s*=\s*(\d+)",line)
				if m:
					height=m.group(1)
			else:
				break
		f.close()
		args.append("-size")
		args.append(width+"x"+height)
	if parent.process:
		try:
			parent.process.terminate()
		except Exception:
			pass
	if sublime.platform()=="osx":
		parent.process=subprocess.Popen(args)
	elif sublime.platform()=="windows":
		parent.process=subprocess.Popen(args)


class LuaNewFileCommand(sublime_plugin.WindowCommand):
	def run(self, dirs):
		self.window.run_command("hide_panel")
		title = "untitle"
		on_done = functools.partial(self.on_done, dirs[0])
		v = self.window.show_input_panel(
			"File Name:", title + ".lua", on_done, None, None)
		v.sel().clear()
		v.sel().add(sublime.Region(0, len(title)))

	def on_done(self, path, name):
		filePath = os.path.join(path, name)
		if os.path.exists(filePath):
			sublime.error_message("Unable to create file, file exists.")
		else:
			code = luaTemplate
			# add attribute
			settings = helper.loadSettings("QuickXDev")
			format = settings.get("date_format", "%Y-%m-%d %H:%M:%S")
			date = datetime.datetime.now().strftime(format)
			code = code.replace("${date}", date)
			author=settings.get("author", "Your Name")
			code = code.replace("${author}", author)
			# save
			helper.writeFile(filePath, code)
			v=sublime.active_window().open_file(filePath)
			# cursor
			v.run_command("insert_snippet",{"contents":code})
			sublime.status_message("Lua file create success!")

	def is_enabled(self, dirs):
		return len(dirs) == 1


class QuickxSmartRunWithPlayerCommand(sublime_plugin.TextCommand):
	def __init__(self,window):
		super(QuickxSmartRunWithPlayerCommand,self).__init__(window)
		self.process=None


	def run(self, edit):
		# find script path
		file_path = self.view.file_name()
		scripts_path = getScriptsPath(file_path)

		if scripts_path == "":
			return

		# root
		quick_cocos2dx_root = checkRoot()
		if not quick_cocos2dx_root:
			return
		run_player_with_path(self, quick_cocos2dx_root, scripts_path)


class QuickxRunWithPlayerCommand(sublime_plugin.WindowCommand):
	def __init__(self,window):
		super(QuickxRunWithPlayerCommand,self).__init__(window)
		self.process=None

	def run(self, dirs):
		# root
		quick_cocos2dx_root = checkRoot()
		if not quick_cocos2dx_root:
			return

		run_player_with_path(self, quick_cocos2dx_root, dirs[0])


	def is_enabled(self, dirs):
		if len(dirs)!=1:
			return False
		mainLuaPath=dirs[0]+"/main.lua"
		if not os.path.exists(mainLuaPath):
			return False
		return True

	def is_visible(self, dirs):
		return self.is_enabled(dirs)


class QuickxGotoDefinitionCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		# select text
		sel=self.view.substr(self.view.sel()[0])
		if len(sel)==0:
			return
		quick_cocos2dx_root = checkRoot()
		if not quick_cocos2dx_root:
			return
		# find all match file
		matchList=[]
		showList=[]
		for item in DEFINITION_LIST:
			for key in item[0]:
				if key==sel:
					matchList.append(item)
					showList.append(item[1])
		for item in USER_DEFINITION_LIST:
			for key in item[0]:
				if key==sel:
					matchList.append(item)
					showList.append(item[1])
		if len(matchList)==0:
			sublime.status_message("Can not find definition '%s'"%(sel))
		elif len(matchList)==1:
			filepath=os.path.join(quick_cocos2dx_root,matchList[0][2])
			if os.path.exists(filepath):
				self.view.window().open_file(filepath+":"+str(matchList[0][3]),sublime.ENCODED_POSITION)
			else:
				sublime.status_message("%s not exists"%(filepath))
		else:
			# multi match
			self.matchList=matchList
			self.quick_cocos2dx_root=quick_cocos2dx_root
			on_done = functools.partial(self.on_done)
			self.view.window().show_quick_panel(showList,on_done)

	def on_done(self,index):
		if index==-1:
			return
		item=self.matchList[index]
		filepath=os.path.join(self.quick_cocos2dx_root,item[2])
		filepath=os.path.abspath(filepath)
		if os.path.exists(filepath):
			self.view.window().open_file(filepath+":"+str(item[3]),sublime.ENCODED_POSITION)
		else:
			sublime.status_message("%s not exists"%(filepath))

	def is_enabled(self):
		return helper.checkFileExt(self.view.file_name(),"lua")

	def is_visible(self):
		return self.is_enabled()


class QuickxRebuildUserDefinitionCommand(sublime_plugin.WindowCommand):
	def __init__(self,window):
		super(QuickxRebuildUserDefinitionCommand,self).__init__(window)
		self.lastTime=0

	def run(self, dirs):
		curTime=time.time()
		if curTime-self.lastTime<3:
			sublime.status_message("Rebuild frequently!")
			return
		self.lastTime=curTime
		global USER_DEFINITION_LIST
		USER_DEFINITION_LIST=rebuild.rebuild(dirs[0],TEMP_PATH)
		path=os.path.join(TEMP_PATH, "user_definition.json")
		data=json.dumps(USER_DEFINITION_LIST)
		if not os.path.exists(TEMP_PATH):
			os.makedirs(TEMP_PATH)
		helper.writeFile(path,data)
		sublime.status_message("Rebuild user definition complete!")

	def is_enabled(self, dirs):
		return len(dirs)==1

	def is_visible(self, dirs):
		return self.is_enabled(dirs)

class QuickxCreateNewProjectCommand(sublime_plugin.WindowCommand):
	def run(self, dirs):
		quick_cocos2dx_root = checkRoot()
		if not quick_cocos2dx_root:
			return
		cmdPath=""
		if sublime.platform()=="osx":
			cmdPath=quick_cocos2dx_root+"/bin/create_project.sh"
		elif sublime.platform()=="windows":
			cmdPath=quick_cocos2dx_root+"/bin/create_project.bat"
		if cmdPath=="" or not os.path.exists(cmdPath):
			sublime.error_message("command no exists")
			return
		self.cmdPath=cmdPath
		self.window.run_command("hide_panel")
		packageName="com.mygames.game01"
		on_done = functools.partial(self.on_done, dirs[0])
		v = self.window.show_input_panel(
			"Package Name:", packageName, on_done, None, None)
		v.sel().clear()
		v.sel().add(sublime.Region(0, len(packageName)))

	def on_done(self, path, packageName):
		if packageName=="":
			sublime.error_message("PackageName must not empty!")
			return
		dotIndex=packageName.rfind(".")
		if dotIndex==-1:
			sublime.error_message("PackageName must two levels,i.e. 'com.game01'.")
			return
		dirName=packageName[dotIndex+1:]
		for item in os.listdir(path):
			if item==dirName:
				sublime.error_message("Folder '%s' already exists."%(dirName))
				return
		args=[self.cmdPath,"-p",packageName]
		if sublime.platform()=="osx":
			subprocess.Popen(args,cwd=path)
		elif sublime.platform()=="windows":
			child=subprocess.Popen(args,cwd=path)
			child.wait()
			self.window.run_command("refresh_folder_list")

	def is_enabled(self, dirs):
		return len(dirs)==1

	def is_visible(self, dirs):
		return self.is_enabled(dirs)

class QuickxRunWithAndroidCommand(sublime_plugin.TextCommand):
	
	def run(self, edit):
		# get environment
		env = getEnvironment()
		if not env:
			return

		# find script path
		file_path = self.view.file_name()
		android_path = getAndroidPath(file_path)

		if android_path == "":
			return
			
		cmdPath=""
		if sublime.platform()=="osx":
			cmdPath=android_path+"/build_native.sh"
		elif sublime.platform()=="windows":
			cmdPath=android_path+"/build_native.bat"
		
		if not os.path.exists(cmdPath):
			sublime.error_message("build_native no exists")
			return

		print("------------------------build_native start------------------------")

		args=["sh",cmdPath]
		process = subprocess.Popen(
			args,
			env=env,
			stdin=subprocess.PIPE, 
			stdout=subprocess.PIPE, 
			stderr=subprocess.STDOUT
		)

		stdout=process.communicate()
		for o in stdout:
			if o :
				lines = o.decode().split("\n")
				for line in lines:
					print(line)

		print("------------------------build_native done------------------------\n\n")

		print("------------------------adb install begin------------------------")
		args=["sh",cmdPath]
				process = subprocess.Popen(
					args,
					env=env,
					stdin=subprocess.PIPE, 
					stdout=subprocess.PIPE, 
					stderr=subprocess.STDOUT
				)

		stdout=process.communicate()
		for o in stdout:
			if o :
				lines = o.decode().split("\n")
				for line in lines:
					print(line)

		print("------------------------build_native done------------------------")

	

class QuickxCompileScriptsCommand(sublime_plugin.WindowCommand):
	def run(self, dirs):
		settings = helper.loadSettings("QuickXDev")
		quick_cocos2dx_root = settings.get("quick_cocos2dx_root", "")
		if len(quick_cocos2dx_root)==0:
			sublime.error_message("quick_cocos2dx_root no set")
			return
		cmdPath=""
		if sublime.platform()=="osx":
			cmdPath=quick_cocos2dx_root+"/bin/compile_scripts.sh"
		elif sublime.platform()=="windows":
			cmdPath=quick_cocos2dx_root+"/bin/compile_scripts.bat"
			if not os.path.exists(cmdPath):
				helper.writeFile(cmdPath,compile_scripts_bat)
		if cmdPath=="" or not os.path.exists(cmdPath):
			sublime.error_message("compile_scripts no exists")
			return
		self.cmdPath=cmdPath
		self.compile_scripts_key=settings.get("compile_scripts_key", "")
		self.window.run_command("hide_panel")
		output="res/game.zip"
		on_done = functools.partial(self.on_done, dirs[0])
		v = self.window.show_input_panel(
			"Output File:", output, on_done, None, None)
		v.sel().clear()
		v.sel().add(sublime.Region(4, 8))

	def on_done(self, path, output):
		if output=="":
			sublime.error_message("Output File must not empty!")
			return
		arr=os.path.split(path)
		path=arr[0]
		src=arr[1]
		args=[self.cmdPath,"-i",src,"-o",output]
		if self.compile_scripts_key!="":
			args.append("-e")
			args.append("xxtea_zip")
			args.append("-ek")
			args.append(self.compile_scripts_key)
		if sublime.platform()=="osx":
			subprocess.Popen(args,cwd=path,env={"luajit":"/usr/local/bin/luajit"})
		elif sublime.platform()=="windows":
			child=subprocess.Popen(args,cwd=path)
			child.wait()
			self.window.run_command("refresh_folder_list")

	def is_enabled(self, dirs):
		return len(dirs)==1

	def is_visible(self, dirs):
		return self.is_enabled(dirs)

class QuickxListener(sublime_plugin.EventListener):
	def __init__(self):
		self.lastTime=0

	def on_post_save(self, view):
		filename=view.file_name()
		if not filename:
			return
		if not helper.checkFileExt(filename,"lua"):
			return
		# rebuild user definition
		curTime=time.time()
		if curTime-self.lastTime<2:
			return
		self.lastTime=curTime
		a=rebuild.rebuildSingle(filename,TEMP_PATH)
		arr=a[0]
		path=a[1]
		# remove prev
		global USER_DEFINITION_LIST
		for i in range(len(USER_DEFINITION_LIST)-1,0,-1):
			item=USER_DEFINITION_LIST[i]
			if item[2]==path:
				USER_DEFINITION_LIST.remove(item)
		USER_DEFINITION_LIST.extend(arr)
		path=os.path.join(TEMP_PATH, "user_definition.json")
		data=json.dumps(USER_DEFINITION_LIST)
		if not os.path.exists(TEMP_PATH):
			os.makedirs(TEMP_PATH)
		helper.writeFile(path,data)
		sublime.status_message("Current file definition rebuild complete!")

# st3
def plugin_loaded():
	sublime.set_timeout(init, 200)

# st2
if not helper.isST3():
	init()

