@echo off
rem wicked-garden launcher - Windows twin of scripts\wicked-garden.mjs (the implementation).
rem Needs node (>= 20) on PATH. The logic lives once, in wicked-garden.mjs.
node "%~dp0wicked-garden.mjs" %*
