main.py - aplikacja  
ui2.py - skompilowany kod ui  
ui2.ui - plik ui dla Qt Designer  
about.ui/about.py - pliki dla okienka "About"  

# Kompilacja pliku UI 

pyuic5 ui2.ui -o ui2.py
or
python -m PyQt5.uic.pyuic -o ui2.py ui2.ui
