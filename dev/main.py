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

        self.original_image = None 
        self.working_pil_image = None 
        self.original_pixmap = None
        self.enabled_cropping = False
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.zoom_step = 0.25
        self.ui.viewport.setAlignment(QtCore.Qt.AlignCenter)

        self.rubber_band = None
        self.crop_origin = None

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
        self.ui.actionCrop.triggered.connect(self.crop_enable)
        self.ui.zoomInButton.clicked.connect(self.zoom_in)
        self.ui.zoomOutButton.clicked.connect(self.zoom_out)
        self.ui.pushButton.clicked.connect(self.open_color_picker)
        self.ui.actionColor_picker.triggered.connect(self.open_color_picker)

        self.add_shadow(self.ui.toolBar)
        self.add_shadow(self.ui.scrollArea)

    def show_about_dialog(self):
        dialog = AboutDialog(self)
        dialog.exec_()

    def crop_enable(self):
        if self.enabled_cropping:
            self.enabled_cropping = False
        else:
            self.enabled_cropping = True

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
        if pil_image is None:
            return QtGui.QPixmap()
        if pil_image.mode not in ['RGB', 'RGBA']:
            pil_image = pil_image.convert('RGBA')
        elif pil_image.mode == 'RGB':
             pil_image = pil_image.convert('RGBA')


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
        if self.original_image: # Zmiana, aby odnosić się do original_image jako bazy
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
        if self.original_pixmap and not self.original_pixmap.isNull():
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

    # image crop
    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if self.working_pil_image is not None and event.button() == QtCore.Qt.LeftButton and self.enabled_cropping:
            self.rect_moved = False
            pos_in_viewport = self.ui.viewport.mapFrom(self, event.pos())
            if self.ui.viewport.rect().contains(pos_in_viewport):
                if self.ui.viewport.pixmap() and not self.ui.viewport.pixmap().isNull():
                    self.crop_origin = pos_in_viewport
                    if not self.rubber_band:
                        self.rubber_band = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, self.ui.viewport)
                    self.rubber_band.setGeometry(QtCore.QRect(self.crop_origin, QtCore.QSize()))
                    self.rubber_band.show()
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self.crop_origin and self.rubber_band and self.enabled_cropping:
            self.rect_moved = True
            current_pos_in_viewport = self.ui.viewport.mapFrom(self, event.pos())
            self.rubber_band.setGeometry(QtCore.QRect(self.crop_origin, current_pos_in_viewport).normalized())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if self.enabled_cropping:
            if self.crop_origin and self.rubber_band and self.rect_moved and event.button() == QtCore.Qt.LeftButton:
                end_pos_in_viewport = self.ui.viewport.mapFrom(self, event.pos())
                selection_rect_vp_coords = QtCore.QRect(self.crop_origin, end_pos_in_viewport).normalized()
                self.rect_moved = False
                selection_rect_vp_coords = selection_rect_vp_coords.intersected(self.ui.viewport.rect())
                self.rubber_band.hide()
                current_display_pixmap = self.ui.viewport.pixmap()
                if self.working_pil_image and \
                   current_display_pixmap and not current_display_pixmap.isNull() and \
                   selection_rect_vp_coords.isValid() and \
                   selection_rect_vp_coords.width() > 0 and selection_rect_vp_coords.height() > 0:

                    spw = current_display_pixmap.width()
                    sph = current_display_pixmap.height()

                    offset_x = (self.ui.viewport.width() - spw) / 2
                    offset_y = (self.ui.viewport.height() - sph) / 2

                    crop_x_on_scaled_pm = selection_rect_vp_coords.x() - offset_x
                    crop_y_on_scaled_pm = selection_rect_vp_coords.y() - offset_y
                    crop_w_on_scaled_pm = selection_rect_vp_coords.width()
                    crop_h_on_scaled_pm = selection_rect_vp_coords.height()

                    crop_x_on_scaled_pm = max(0, crop_x_on_scaled_pm)
                    crop_y_on_scaled_pm = max(0, crop_y_on_scaled_pm)

                    if crop_x_on_scaled_pm >= spw or crop_y_on_scaled_pm >= sph: 
                        self.crop_origin = None
                        event.accept()
                        return

                    crop_w_on_scaled_pm = min(crop_w_on_scaled_pm, spw - crop_x_on_scaled_pm)
                    crop_h_on_scaled_pm = min(crop_h_on_scaled_pm, sph - crop_y_on_scaled_pm)

                    if crop_w_on_scaled_pm > 0 and crop_h_on_scaled_pm > 0:
                        pil_crop_x1 = int(crop_x_on_scaled_pm / self.zoom_factor)
                        pil_crop_y1 = int(crop_y_on_scaled_pm / self.zoom_factor)
                        pil_crop_w = int(crop_w_on_scaled_pm / self.zoom_factor)
                        pil_crop_h = int(crop_h_on_scaled_pm / self.zoom_factor)

                        pil_crop_x2 = pil_crop_x1 + pil_crop_w
                        pil_crop_y2 = pil_crop_y1 + pil_crop_h

                        final_crop_box = (
                            max(0, pil_crop_x1),
                            max(0, pil_crop_y1),
                            min(self.working_pil_image.width, pil_crop_x2),
                            min(self.working_pil_image.height, pil_crop_y2)
                        )
                        if final_crop_box[2] > final_crop_box[0] and final_crop_box[3] > final_crop_box[1]:
                            try:
                                cropped_pil = self.working_pil_image.crop(final_crop_box)
                                self.working_pil_image = cropped_pil
                                self.original_pixmap = self.pil_image_to_pixmap(self.working_pil_image) 
                                self.update_display()
                            except Exception as e:
                                print(f"Błąd przycinania: {e}")
                self.crop_origin = None
                event.accept()
                return
            if self.rubber_band:
                 self.rubber_band.hide()
            self.crop_origin = None
            super().mouseReleaseEvent(event)


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