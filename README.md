# Filtroo — Simple Image Editor

Filtroo is a university group project developed as part of a Software Engineering course. The goal was to go through all key stages of the software development lifecycle:

- Concept design  
- Planning  
- Requirements analysis  
- Development  
- Testing  
- Release

---

## Project Overview

Filtroo is a lightweight photo editor that provides essential tools for basic image manipulation. Key features include:

- Image cropping  
- Image compression  
- Mirroring and rotation  
- Color adjustment  
- Image filters  
- Enhancements

---

## Tech Stack

The project is written in Python and uses the following libraries and tools:

- PyQt5 (Qt for Python) — GUI framework  
- Pillow (PIL) — image processing  
- Standard Python modules: sys, os, time  

---

## Launching the App

The compiled application can be launched via:

dist/filtroo.exe

For development, you can also run:

python main.py

---

## 🛠️ Developer Notes

- UI was designed using Qt Designer  
- To compile the .ui file into Python:  
  pyuic5 ui2.ui -o ui2.py  
  or  
  python -m PyQt5.uic.pyuic -o ui2.py ui2.ui  

- To compile Qt resources (res.qrc):  
  pyrcc5 res.qrc -o res.py

The main entry point is main.py.

---

## 📁 Project Structure (example)

- main.py — application entry point  
- ui2.ui / ui2.py — main UI file and compiled version
- about.ui / about.py - aditional UI file for about-menu  
- res.qrc / res.py — Qt resource file and compiled version  
- Ikony_inż/ — image assets (icons, etc.)  
