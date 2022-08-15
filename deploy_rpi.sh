find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf
cd ..
rsync -avz -e "ssh -p <PORT>" <SRC> <HOST>:<DEST>