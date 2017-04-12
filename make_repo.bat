mkdir %TEMP%\gitplot
pushd %TEMP%\gitplot
git init
echo Blah>file_1.txt
git add file_1.txt
git commit -m "Adding the first file."
popd