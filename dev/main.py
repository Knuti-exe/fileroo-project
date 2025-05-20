import sys, io
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QIcon, QImage, QPixmap
from PyQt5.QtCore import QSize, QBuffer
from PyQt5.QtWidgets import QFileDialog, QColorDialog, QDialog
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
from PIL import Image, ImageEnhance, ImageChops, ImageQt
from ui2 import *                                               
from about import Ui_Dialog

import res_rc



class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        self.ui.Exp.valueChanged.connect(self.slider_changed)
        self.ui.actionAbout.triggered.connect(self.show_about_dialog)

        self.original_pixmap = None
        self.original_pil_image = None
        self.working_pil_image = None
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.zoom_step = 0.25
        self.ui.viewport.setAlignment(QtCore.Qt.AlignCenter)

        panel1 = CollapsiblePanel("Color", self.ui.collapsible_1)
        panel2 = CollapsiblePanel("Contrast", self.ui.collapsible_2)

        layout = self.ui.verticalLayout_2
        for i in reversed(range(layout.count())):
            item = layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

        layout.addWidget(panel1)
        layout.addWidget(panel2)


        self.ui.actionOpen.triggered.connect(self.open_file)
        self.ui.zoomInButton.clicked.connect(self.zoom_in)
        self.ui.zoomOutButton.clicked.connect(self.zoom_out)
        self.ui.pushButton.clicked.connect(self.open_color_picker)
        self.ui.actionColor_picker.triggered.connect(self.open_color_picker)

        self.add_shadow(self.ui.toolBar)
        self.add_shadow(self.ui.scrollArea)

    def show_about_dialog(self):
        dialog = AboutDialog(self)
        dialog.exec_()

    def open_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, 
            "Open File", 
            "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if filename:
            self.original_image = Image.open(filename).convert("RGB")
            self.working_pil_image = self.original_image.copy()
            self.original_pixmap = self.pil_image_to_pixmap(self.working_pil_image)
            self.zoom_factor = 1.0
            self.update_display()
            self.update_exp() 
            self.ui.statusbar.showMessage(f"Opened: {filename}")
            

    def pil_image_to_pixmap(self, pil_image):
        """Convert a Pillow Image to QPixmap using bytes buffer"""
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(buffer.getvalue())
        return pixmap

    def open_color_picker(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.apply_color(color)

    def apply_color(self, color):
        if self.working_pil_image is None:
            return

        r, g, b, _ = color.getRgb()

        # Convert to RGB if necessary
        if self.working_pil_image.mode != 'RGB':
            img = self.working_pil_image.convert('RGB')
        else:
            img = self.working_pil_image.copy()

        # Create tint image and apply multiply
        tint = Image.new('RGB', img.size, (r, g, b))
        tinted = ImageChops.multiply(img, tint)

        self.working_pil_image = tinted
        self.original_pixmap = self.pil_image_to_pixmap(self.working_pil_image)
        self.update_display()

    def slider_changed(self):
        if self.working_pil_image:
            self.update_exp()

    def update_exp(self):
        if self.original_image is None:
            return

        exp_value = self.ui.Exp.value() / 20  # scale value
        enhancer = ImageEnhance.Brightness(self.original_image)
        modified = enhancer.enhance(2 ** exp_value)

        self.working_pil_image = modified
        self.original_pixmap = self.pil_image_to_pixmap(modified)
        self.update_display()

    def zoom_in(self):
        self.zoom_factor = min(self.zoom_factor + self.zoom_step, self.max_zoom)
        self.update_display()

    def zoom_out(self):
        self.zoom_factor = max(self.zoom_factor - self.zoom_step, self.min_zoom)
        self.update_display()

    def update_display(self):
        if self.original_pixmap:
            scaled_size = self.original_pixmap.size() * self.zoom_factor
            scaled_pixmap = self.original_pixmap.scaled(
                scaled_size, 
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            self.ui.viewport.setPixmap(scaled_pixmap)
            
    def add_shadow(self, widget, blur_radius=15, x_offset=5, y_offset=5, color=QtGui.QColor(0, 0, 0, 160)):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur_radius)
        shadow.setXOffset(x_offset)
        shadow.setYOffset(y_offset)
        shadow.setColor(color)
        widget.setGraphicsEffect(shadow)

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle("About")
        self.setFixedSize(self.size())

class CollapsiblePanel(QtWidgets.QWidget):
    def __init__(self, title: str, content: QtWidgets.QWidget, parent=None):
        super().__init__(parent)

        self.toggle_button = QtWidgets.QToolButton(text=title, checkable=True, checked=False)
        self.toggle_button.setStyleSheet("QToolButton { background-color: #444; color: white; }")
        self.toggle_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(QtCore.Qt.RightArrow)
        self.toggle_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.toggle_button.clicked.connect(self.toggle)
        self.toggle_button.setStyleSheet("""
            QToolButton {
                background-color: #444;
                color: white;
                border: none;
                padding: 5px;
                text-align: left;
                font-weight: bold;
            }
            QToolButton:checked {
                background-color: #666;
            }
            QToolButton::menu-indicator { image: none; }
        """)

        self.content_area = QtWidgets.QScrollArea()
        self.content_area.setMaximumHeight(0)
        self.content_area.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.content_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.content_area.setStyleSheet("background-color: #666;")
        self.content_area.setWidgetResizable(True)
        self.content_area.setWidget(content)

        self.toggle_animation = QtCore.QPropertyAnimation(self.content_area, b"maximumHeight")
        self.toggle_animation.setDuration(200)
        self.toggle_animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        

    def toggle(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)

        content_height = self.content_area.widget().sizeHint().height()
        start_value = self.content_area.maximumHeight()
        end_value = content_height if checked else 0

        self.toggle_animation.stop()
        self.toggle_animation.setStartValue(start_value)
        self.toggle_animation.setEndValue(end_value)
        self.toggle_animation.start()



if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
