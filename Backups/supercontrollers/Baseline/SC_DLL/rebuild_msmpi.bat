@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
call "C:\Program Files (x86)\Intel\oneAPI\compiler\latest\env\vars.bat"
cd /D "D:\2_PhD_UBC\Code\FASTv355\5MW_Baseline\ServoData\SC_DLL\build"
cmake .. -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DCMAKE_Fortran_COMPILER=ifx
cmake --build .
copy /Y SC_DLL.dll "D:\2_PhD_UBC\Code\FASTv355\SteadyWind_ffconnect\SC_DLL.dll"
copy /Y SC_DLL.dll "D:\2_PhD_UBC\Code\FASTv355\SteadyWind_FOWF_ffconnect\SC_DLL.dll"
