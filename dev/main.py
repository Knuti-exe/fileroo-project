import sys, io
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QIcon, QImage, QPixmap
from PyQt5.QtCore import QSize, QBuffer
from PyQt5.QtWidgets import QFileDialog, QColorDialog, QDialog, QLabel
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
from PIL import Image, ImageEnhance, ImageChops, ImageQt
from ui2 import Ui_MainWindow
from about import Ui_Dialog


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.initialize_properties()
        self.setup_ui()
        self.setup_connections()
        self.setup_collapsible_panels()
        self.add_shadows()

    def initialize_properties(self):
        self.original_image = None
        self.working_pil_image = None
        self.original_pixmap = None
        self.enabled_cropping = False
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.zoom_step = 0.25
        self.panning = False
        self.last_pan_point = QtCore.QPoint()
        self.rubber_band = None
        self.crop_origin = None
        self.rect_moved = False
        self.undo_stack = []
        self.redo_stack = []
        self.max_stack_size = 5
        self.max_viewport_size = QtCore.QSize(800, 600)

    def setup_ui(self):
        self.ui.imageLabel = self.ui.scrollArea_viewport.findChild(QLabel, "imageLabel")
        self.ui.imageLabel.setAlignment(QtCore.Qt.AlignCenter)



        self.ui.scrollArea_viewport.setAlignment(QtCore.Qt.AlignCenter)
        self.ui.scrollArea_viewport.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.ui.scrollArea_viewport.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

    def setup_connections(self):
        # Menu actions
        self.ui.actionOpen.triggered.connect(self.open_file)
        self.ui.actionCrop.triggered.connect(self.toggle_cropping)
        self.ui.actionAbout.triggered.connect(self.show_about_dialog)
        self.ui.actionColor_picker.triggered.connect(self.open_color_picker)
        self.ui.actionUndo.triggered.connect(self.undo)
        self.ui.actionRedo.triggered.connect(self.redo)

        # Zoom slider
        # self.ui.zoomInButton.clicked.connect(self.zoom_in)
        # self.ui.zoomOutButton.clicked.connect(self.zoom_out)
        self.ui.zoomSlider.valueChanged.connect(self.zoom)

        # Right toolbar
        self.ui.pushButton.clicked.connect(self.open_color_picker)
        self.ui.Exp.valueChanged.connect(self.update_exposure)

        # Event filters
        self.ui.scrollArea_viewport.viewport().installEventFilter(self)

    def setup_collapsible_panels(self):
        layout = self.ui.verticalLayout_2
        for i in reversed(range(layout.count())):
            if item := layout.itemAt(i):
                if widget := item.widget():
                    widget.setParent(None)

        self.panels = [
            CollapsiblePanel("Color", self.ui.collapsible_1),
            CollapsiblePanel("Contrast", self.ui.collapsible_2)
        ]

        for panel in self.panels:
            layout.addWidget(panel)

        layout.addStretch(1)

    def add_shadows(self):
        self.add_shadow(self.ui.toolBar)
        self.add_shadow(self.ui.scrollArea)

    # ================ Image Operations =================
    def open_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open File", "", "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if not filename:
            return

        self.original_image = Image.open(filename).convert("RGB")
        self.working_pil_image = self.original_image.copy()
        self.original_pixmap = self.pil_image_to_pixmap(self.working_pil_image)
        self.zoom_factor = 1.0
        self.update_display()
        self.update_exposure()
        self.ui.statusbar.showMessage(f"Opened: {filename}")

    def pil_image_to_pixmap(self, pil_image):
        if not pil_image:
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
        if not self.working_pil_image:
            return

        r, g, b, _ = color.getRgb()
        img = self.working_pil_image.convert('RGB') if self.working_pil_image.mode != 'RGB' else self.working_pil_image.copy()

        tint = Image.new('RGB', img.size, (r, g, b))
        tinted = ImageChops.multiply(img, tint)

        self.push_undo_state()
        self.working_pil_image = tinted
        self.original_pixmap = self.pil_image_to_pixmap(tinted)
        self.update_display()

    def update_exposure(self):
        if not self.original_image:
            return

        exp_value = self.ui.Exp.value() / 20
        enhancer = ImageEnhance.Brightness(self.original_image)
        modified = enhancer.enhance(2 ** exp_value)

        self.push_undo_state()
        self.working_pil_image = modified
        self.original_pixmap = self.pil_image_to_pixmap(modified)
        self.update_display()

    # def zoom_in(self):
    #     self.zoom_factor = min(self.zoom_factor + self.zoom_step, self.max_zoom)
    #     self.update_display()
    #
    # def zoom_out(self):
    #     self.zoom_factor = max(self.zoom_factor - self.zoom_step, self.min_zoom)
    #     self.update_display()
    def zoom(self, value):
        self.zoom_factor = value / 100.0

        if self.zoom_factor < self.min_zoom:
            self.zoom_factor = self.min_zoom
        elif self.zoom_factor > self.max_zoom:
            self.zoom_factor = self.max_zoom

        percent = int(self.zoom_factor * 100)
        self.ui.zoomLabel.setText(f"{percent}%")
        self.update_display()
    # ================ Undo/Redo Operations =================
    def push_undo_state(self):
        if not self.working_pil_image:
            return

        self.undo_stack.append(self.working_pil_image.copy())
        if len(self.undo_stack) > self.max_stack_size:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.working_pil_image.copy())
            self.working_pil_image = self.undo_stack.pop()
            self.original_pixmap = self.pil_image_to_pixmap(self.working_pil_image)
            self.update_display()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.working_pil_image.copy())
            self.working_pil_image = self.redo_stack.pop()
            self.original_pixmap = self.pil_image_to_pixmap(self.working_pil_image)
            self.update_display()

    # ================ Display Operations =================
    def update_display(self):
        if not self.original_pixmap or self.original_pixmap.isNull():
            return

        scaled_size = self.original_pixmap.size() * self.zoom_factor
        scaled_pixmap = self.original_pixmap.scaled(
            scaled_size,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )

        self.ui.imageLabel.setPixmap(scaled_pixmap)
        # viewport_size = scaled_size.boundedTo(self.max_viewport_size)
        self.ui.imageLabel.resize(scaled_pixmap.size())

        # Set scroll area size
        self.ui.scrollArea_viewport.setMinimumSize(
            min(scaled_size.width(), self.max_viewport_size.width()),
            min(scaled_size.height(), self.max_viewport_size.height())
        )
        self.ui.scrollArea_viewport.setMaximumSize(self.max_viewport_size)
    

    def add_shadow(self, widget, blur_radius=15, x_offset=5, y_offset=5, color=QtGui.QColor(0, 0, 0, 160)):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur_radius)
        shadow.setXOffset(x_offset)
        shadow.setYOffset(y_offset)
        shadow.setColor(color)
        widget.setGraphicsEffect(shadow)

    # ================ Crop and mouse =================
    def toggle_cropping(self):
        self.enabled_cropping = not self.enabled_cropping

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if (self.working_pil_image and
            event.button() == QtCore.Qt.LeftButton and
            self.enabled_cropping):

            self.rect_moved = False
            pos_in_viewport = self.ui.imageLabel.mapFrom(self, event.pos())

            if (self.ui.imageLabel.rect().contains(pos_in_viewport) and
                self.ui.imageLabel.pixmap() and
                not self.ui.imageLabel.pixmap().isNull()):

                self.crop_origin = pos_in_viewport
                if not self.rubber_band:
                    self.rubber_band = QtWidgets.QRubberBand(
                        QtWidgets.QRubberBand.Rectangle,
                        self.ui.imageLabel
                    )
                self.rubber_band.setGeometry(QtCore.QRect(self.crop_origin, QtCore.QSize()))
                self.rubber_band.show()
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self.crop_origin and self.rubber_band and self.enabled_cropping:
            self.rect_moved = True
            current_pos_in_viewport = self.ui.imageLabel.mapFrom(self, event.pos())
            self.rubber_band.setGeometry(QtCore.QRect(self.crop_origin, current_pos_in_viewport).normalized())
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if (self.enabled_cropping and
            self.crop_origin and
            self.rubber_band and
            self.rect_moved and
            event.button() == QtCore.Qt.LeftButton):

            end_pos_in_viewport = self.ui.imageLabel.mapFrom(self, event.pos())
            selection_rect_vp_coords = QtCore.QRect(self.crop_origin, end_pos_in_viewport).normalized()
            self.rect_moved = False
            selection_rect_vp_coords = selection_rect_vp_coords.intersected(self.ui.imageLabel.rect())
            self.rubber_band.hide()

            current_display_pixmap = self.ui.imageLabel.pixmap()
            if (self.working_pil_image and
                current_display_pixmap and
                not current_display_pixmap.isNull() and
                selection_rect_vp_coords.isValid() and
                selection_rect_vp_coords.width() > 0 and
                selection_rect_vp_coords.height() > 0):

                self.process_crop(selection_rect_vp_coords, current_display_pixmap)

            self.crop_origin = None
            event.accept()
            return

        if self.rubber_band:
            self.rubber_band.hide()
        self.crop_origin = None
        super().mouseReleaseEvent(event)

    def process_crop(self, selection_rect_vp_coords, current_display_pixmap):
        spw = current_display_pixmap.width()
        sph = current_display_pixmap.height()
        offset_x = (self.ui.imageLabel.width() - spw) / 2
        offset_y = (self.ui.imageLabel.height() - sph) / 2

        crop_x = max(0, selection_rect_vp_coords.x() - offset_x)
        crop_y = max(0, selection_rect_vp_coords.y() - offset_y)
        crop_w = min(selection_rect_vp_coords.width(), spw - crop_x)
        crop_h = min(selection_rect_vp_coords.height(), sph - crop_y)

        if crop_w <= 0 or crop_h <= 0 or crop_x >= spw or crop_y >= sph:
            return

        pil_crop_x1 = int(crop_x / self.zoom_factor)
        pil_crop_y1 = int(crop_y / self.zoom_factor)
        pil_crop_x2 = int((crop_x + crop_w) / self.zoom_factor)
        pil_crop_y2 = int((crop_y + crop_h) / self.zoom_factor)

        pil_crop_x1 = max(0, pil_crop_x1)
        pil_crop_y1 = max(0, pil_crop_y1)
        pil_crop_x2 = min(self.working_pil_image.width, pil_crop_x2)
        pil_crop_y2 = min(self.working_pil_image.height, pil_crop_y2)

        if pil_crop_x2 <= pil_crop_x1 or pil_crop_y2 <= pil_crop_y1:
            return

        try:
            self.push_undo_state()
            self.working_pil_image = self.working_pil_image.crop(
                (pil_crop_x1, pil_crop_y1, pil_crop_x2, pil_crop_y2)
            )
            self.original_pixmap = self.pil_image_to_pixmap(self.working_pil_image)
            self.update_display()
        except Exception as e:
            print(f"Crop error: {e}")

    # ================ Event Handling =================
    def eventFilter(self, source, event):
        if source is self.ui.scrollArea_viewport.viewport():
            if event.type() == QtCore.QEvent.MouseButtonPress:
                if event.buttons() == QtCore.Qt.MiddleButton:
                    self.panning = True
                    self.last_pan_point = event.pos()
                    QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.ClosedHandCursor)
                    return True

            elif event.type() == QtCore.QEvent.MouseMove and self.panning:
                delta = event.pos() - self.last_pan_point
                self.last_pan_point = event.pos()
                h_bar = self.ui.scrollArea_viewport.horizontalScrollBar()
                v_bar = self.ui.scrollArea_viewport.verticalScrollBar()
                h_bar.setValue(h_bar.value() - delta.x())
                v_bar.setValue(v_bar.value() - delta.y())
                return True

            elif event.type() == QtCore.QEvent.MouseButtonRelease:
                if event.button() == QtCore.Qt.MiddleButton and self.panning:
                    self.panning = False
                    QtWidgets.QApplication.restoreOverrideCursor()
                    return True

        return super().eventFilter(source, event)


    def show_about_dialog(self):
        dialog = AboutDialog(self)
        dialog.exec_()

    # ================ About window =================
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

        self.stretch = QtWidgets.QSpacerItem(
            20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)
        main_layout.addItem(self.stretch)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

    def toggle(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)
        content_height = self.content_area.widget().sizeHint().height()
        self.toggle_animation.setStartValue(self.content_area.maximumHeight())
        self.toggle_animation.setEndValue(content_height if checked else 0)
        self.toggle_animation.start()

        if checked:
            self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
            self.content_area.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        else:
            self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
            self.content_area.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
