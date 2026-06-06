@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
call "C:\Program Files (x86)\Intel\oneAPI\compiler\latest\env\vars.bat"
cd /D "D:\2_PhD_UBC\Code\FASTv355\5MW_Baseline\ServoData\DISCON_OC3_MPI_repositioning\build"
cmake .. -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DCMAKE_Fortran_COMPILER=ifx
cmake --build .
copy /Y DISCON_OC3Hywind_MPI_repositioning.dll "D:\2_PhD_UBC\Code\FASTv355\5MW_Baseline\ServoData\DISCON_OC3Hywind_MPI_repositioning.dll"
copy /Y DISCON_OC3Hywind_MPI_repositioning.dll "D:\2_PhD_UBC\Code\FASTv355\5MW_Baseline\ServoData\DISCON_OC3Hywind_MPI_repositioning_WT1.dll"
copy /Y DISCON_OC3Hywind_MPI_repositioning.dll "D:\2_PhD_UBC\Code\FASTv355\5MW_Baseline\ServoData\DISCON_OC3Hywind_MPI_repositioning_WT2.dll"
