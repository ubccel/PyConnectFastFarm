@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
call "C:\Program Files (x86)\Intel\oneAPI\compiler\latest\env\vars.bat"
cd /D "D:\2_PhD_UBC\Code\FASTv355\5MW_Baseline\ServoData\Full\DISCON_OC3_MPI_IPC_Full\build"
cmake .. -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DCMAKE_Fortran_COMPILER=ifx
cmake --build .
copy /Y DISCON_OC3Hywind_MPI_IPC_Full.dll "D:\2_PhD_UBC\Code\FASTv355\5MW_Baseline\ServoData\Full\DISCON_OC3Hywind_MPI_IPC_Full.dll"
