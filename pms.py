import sys
import os
import logging
import configparser
import hashlib
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QLineEdit, QComboBox, QPushButton, QTableView,
                              QTabWidget, QToolBar, QFileDialog, QMessageBox,
                              QStatusBar, QFormLayout, QHeaderView, QCheckBox, QMenu,
                              QDialog, QGraphicsView, QGraphicsScene, QCompleter,
                              QStyledItemDelegate, QProgressBar, QTableWidget,
                              QTableWidgetItem, QGridLayout)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QTimer, Signal, QDateTime, QStringListModel
from PySide6.QtGui import QColor, QPalette, QAction, QIcon, QFont, QBrush, QTextDocument, QPdfWriter, QPageSize, QPixmap
from PySide6.QtSql import QSqlDatabase, QSqlTableModel
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
import sqlite3
from datetime import datetime, timedelta
import csv
import re
import shutil
from dashboard import Dashboard  
import matplotlib.pyplot as plt  

# Determine paths for frozen vs. non-frozen environments
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)  # Directory where EXE is located
    RESOURCE_DIR = BASE_DIR  # Nuitka standalone puts files in the same dir
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = BASE_DIR

# Ensure BASE_DIR exists
if not os.path.exists(BASE_DIR):
    try:
        os.makedirs(BASE_DIR)
    except Exception as e:
        print(f"Failed to create BASE_DIR: {e}")
        raise

# Constants
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "products.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")
LOG_PATH = os.path.join(BASE_DIR, "app.log")
APP_ICON = os.path.join(BASE_DIR, "app.png")
VERSION = "1.0"
VALID_LICENSE_KEY = "PMS-2025-PROD-MGMT"
LICENSE_HASH = hashlib.sha256(VALID_LICENSE_KEY.encode()).hexdigest()
TOTAL_COLOR = "#000000"
QR_STORAGE_DIR = os.path.join(BASE_DIR, "qr_codes")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

# Modern Color Palette
PRIMARY_BG = "#F8FAFC"
SECONDARY_BG = "#FFFFFF"
ACCENT_COLOR = "#4F46E5"
TEXT_COLOR = "#1E293B"
HEADER_BG = "#1E293B"
HOVER_COLOR = "#6366F1"
BORDER_COLOR = "#E2E8F0"
DELETE_COLOR = "#EF4444"
UPDATE_COLOR = "#F59E0B"
PROFIT_COLOR = "#10B981"
REPLACE_COLOR = "#22C55E"

# Setup logging immediately
try:
    logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info(f"Application starting...")
    logging.info(f"BASE_DIR: {BASE_DIR}")
    logging.info(f"RESOURCE_DIR: {RESOURCE_DIR}")
    logging.info(f"DB_PATH: {DB_PATH}")
    logging.info(f"CONFIG_PATH: {CONFIG_PATH}")
except Exception as e:
    # Fallback to stderr if logging fails (visible only with console=True)
    print(f"Failed to setup logging: {e}")

class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Activate Software")
        self.setFixedSize(400, 350)
        self.setWindowIcon(QIcon(APP_ICON) if os.path.exists(APP_ICON) else QIcon())
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        self.setStyleSheet(f"background-color: {PRIMARY_BG}; border-radius: 8px;")
        
        label = QLabel("Enter License Key to Activate")
        label.setStyleSheet(f"color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 16px; font-weight: bold;")
        layout.addWidget(label, alignment=Qt.AlignCenter)

        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("e.g., ABC-2025-DEFG-HIJK")
        self.company_name_input = QLineEdit()
        self.company_name_input.setPlaceholderText("Enter Company Name")
        self.pan_number_input = QLineEdit()
        self.pan_number_input.setPlaceholderText("Enter PAN Number")

        inputs = [self.license_input, self.company_name_input, self.pan_number_input]
        for widget in inputs:
            widget.setStyleSheet(f"padding: 10px; border: 1px solid {BORDER_COLOR}; border-radius: 6px; background-color: {SECONDARY_BG}; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
            layout.addWidget(widget)

        self.activate_btn = QPushButton("Activate")
        self.activate_btn.setStyleSheet(f"background-color: {ACCENT_COLOR}; color: white; padding: 10px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none;")
        self.activate_btn.clicked.connect(self.verify_license)
        layout.addWidget(self.activate_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {DELETE_COLOR}; font-family: Segoe UI; font-size: 12px; font-weight: bold;")
        layout.addWidget(self.status_label, alignment=Qt.AlignCenter)
        layout.addStretch()

    def verify_license(self):
        entered_key = self.license_input.text().strip()
        company_name = self.company_name_input.text().strip()
        pan_number = self.pan_number_input.text().strip()
        entered_hash = hashlib.sha256(entered_key.encode()).hexdigest()
        if entered_hash == LICENSE_HASH and company_name and pan_number:
            logging.info("License verified")
            self.company_name = company_name
            self.pan_number = pan_number
            self.accept()
        else:
            self.status_label.setText("Invalid License Key or Missing Company/PAN")
            logging.warning("Invalid license attempt")
            QMessageBox.warning(self, "Error", "Invalid license key or missing company name/PAN number!", QMessageBox.Ok)

class LoadingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Activating Software")
        self.setFixedSize(300, 150)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint)
        self.setup_ui()
        self.progress = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(30)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.loading_label = QLabel("Activating Software...")
        self.loading_label.setStyleSheet(f"color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 16px; font-weight: bold;")
        self.loading_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.loading_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {BORDER_COLOR};
                border-radius: 5px;
                background-color: {SECONDARY_BG};
                text-align: center;
                color: {TEXT_COLOR};
                font-family: Segoe UI;
                font-size: 14px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT_COLOR};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.progress_bar)
        layout.addStretch()

    def update_progress(self):
        self.progress += 1
        self.progress_bar.setValue(self.progress)
        if self.progress >= 100:
            self.timer.stop()
            self.accept()

class AdvancedProductFilterModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.filters = {
            'name': '', 'type': '', 'min_buy': None, 'max_buy': None,
            'min_sell': None, 'max_sell': None, 'updated_after': None,
            'name_regex': None, 'stock_min': None, 'stock_max': None
        }
        self.setDynamicSortFilter(True)

    def setFilterCriteria(self, **kwargs):
        for key, value in kwargs.items():
            if key == 'name':
                self.filters[key] = value.lower() if value else ''
                try:
                    self.filters['name_regex'] = re.compile(value, re.IGNORECASE) if value else None
                except re.error:
                    self.filters['name_regex'] = None
            elif key == 'type':
                self.filters[key] = value if value and value != "All Types" else ""
            elif key in self.filters:
                self.filters[key] = value
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        row_data = {
            'name': str(model.index(source_row, 1).data() or "").lower(),
            'type': str(model.index(source_row, 2).data() or ""),
            'buy_price': float(model.index(source_row, 3).data() or 0),
            'sell_price': float(model.index(source_row, 4).data() or 0),
            'last_updated': str(model.index(source_row, 5).data() or ""),
            'stock': int(model.index(source_row, 6).data() or 0)
        }
        conditions = [
            (self.filters['name'] in row_data['name'] or 
             (self.filters['name_regex'] and self.filters['name_regex'].search(row_data['name']))) 
            if self.filters['name'] else True,
            row_data['type'] == self.filters['type'] if self.filters['type'] else True,
            row_data['buy_price'] >= self.filters['min_buy'] if self.filters['min_buy'] is not None else True,
            row_data['buy_price'] <= self.filters['max_buy'] if self.filters['max_buy'] is not None else True,
            row_data['sell_price'] >= self.filters['min_sell'] if self.filters['min_sell'] is not None else True,
            row_data['sell_price'] <= self.filters['max_sell'] if self.filters['max_sell'] is not None else True,
            row_data['last_updated'] >= self.filters['updated_after'] if self.filters['updated_after'] else True,
            row_data['stock'] >= self.filters['stock_min'] if self.filters['stock_min'] is not None else True,
            row_data['stock'] <= self.filters['stock_max'] if self.filters['stock_max'] is not None else True
        ]
        return all(conditions)

    def resetFilters(self):
        self.filters = {key: None if key not in ['name', 'type'] else '' for key in self.filters}
        self.invalidateFilter()

class CategorySelector(QWidget):
    type_selected = Signal(str)
    
    def __init__(self, product_types, parent=None):
        super().__init__(parent)
        self.product_types = product_types
        self.setup_ui()

    def setup_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.button = QPushButton("Select Type")
        self.button.setStyleSheet(f"background-color: {ACCENT_COLOR}; color: white; padding: 8px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none;")
        self.button.clicked.connect(self.show_menu)
        self.layout.addWidget(self.button)
        self.current_type = ""

    def show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background-color: {SECONDARY_BG}; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: 1px solid {BORDER_COLOR}; }} QMenu::item:selected {{ background-color: {HOVER_COLOR}; color: white; }}")
        for category, types in self.product_types:
            if category:
                submenu = menu.addMenu(category)
                for type_ in types:
                    action = submenu.addAction(type_)
                    action.triggered.connect(lambda checked, t=type_: self.select_type(t))
            else:
                action = menu.addAction(types)
                action.triggered.connect(lambda checked, t=types: self.select_type(t))
        menu.exec(self.button.mapToGlobal(self.button.rect().bottomLeft()))

    def select_type(self, type_):
        self.current_type = type_
        self.button.setText(type_ or "Select Type")
        self.type_selected.emit(type_)

    def currentText(self):
        return self.current_type

    def setCurrentText(self, text):
        self.current_type = text
        self.button.setText(text or "Select Type")

class HighlightDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        if index.column() == 6:  # Stock column
            stock = index.data(Qt.DisplayRole)
            if stock == 0:
                option.palette.setColor(QPalette.Text, QColor(DELETE_COLOR))
                option.font.setBold(True)
        super().paint(painter, option, index)

class DamageStatusDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        if index.column() == 5:  # Replaced column
            replaced = index.data(Qt.DisplayRole)
            option.backgroundBrush = QBrush(QColor(REPLACE_COLOR if replaced == 1 else DELETE_COLOR))
        super().paint(painter, option, index)

class ProductManagementApp(QMainWindow):
    low_stock_signal = Signal(str, int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"PMS v{VERSION}")
        self.setGeometry(100, 100, 1400, 800)
        self.setWindowIcon(QIcon(APP_ICON) if os.path.exists(APP_ICON) else QIcon())
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        
        self.config = configparser.ConfigParser()
        self.load_config()

        self.activation_label = QLabel("Not Activated")
        self.company_name = self.config.get('Settings', 'company_name', fallback='')
        self.pan_number = self.config.get('Settings', 'pan_number', fallback='')

        if not self.is_licensed():
            if not self.activate_license():
                sys.exit(1)
        else:
            self.update_activation_status()
        
        self.id_input = QLineEdit()
        self.id_input.setVisible(False)
        
        if not os.path.exists(QR_STORAGE_DIR):
            os.makedirs(QR_STORAGE_DIR)
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)

        try:
            self.setup_databases()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Database setup failed: {e}")
            sys.exit(1)
        
        self.product_names = self.get_product_names()
        self.low_stock_signal.connect(self.show_low_stock_alert)
        self.setup_ui()
        self.load_data()
        self.reconcile_stock()
        logging.info("Application initialized successfully")

        # Setup daily backup timer
        self.backup_timer = QTimer(self)
        self.backup_timer.timeout.connect(self.automatic_backup)
        self.backup_timer.start(86400000)  # Check every 24 hours (in milliseconds)
        self.last_backup_date = self.current_date

    def create_message_box(self, title, text, icon=QMessageBox.Information, buttons=QMessageBox.Ok):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon)
        msg.setStandardButtons(buttons)
        msg.setStyleSheet(f"QMessageBox {{ background-color: {PRIMARY_BG}; border-radius: 8px; }} QMessageBox QLabel {{ color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold; }} QPushButton {{ background-color: {ACCENT_COLOR}; color: white; padding: 8px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none; }} QPushButton:hover {{ background-color: {HOVER_COLOR}; }}")
        return msg

    def load_config(self):
        try:
            if not os.path.exists(CONFIG_PATH):
                self.config['Settings'] = {
                    'theme': 'modern',
                    'backup_dir': BACKUP_DIR,
                    'license_status': '',
                    'company_name': '',
                    'pan_number': ''
                }
                with open(CONFIG_PATH, 'w') as configfile:
                    self.config.write(configfile)
            else:
                self.config.read(CONFIG_PATH)
        except Exception as e:
            logging.error(f"Failed to load or create config: {e}")
            self.config['Settings'] = {
                'theme': 'modern',
                'backup_dir': BACKUP_DIR,
                'license_status': '',
                'company_name': '',
                'pan_number': ''
            }

    def is_licensed(self):
        return self.config.get('Settings', 'license_status', fallback='') == hashlib.sha256("ACTIVATED".encode()).hexdigest()

    def activate_license(self):
        dialog = LicenseDialog(self)
        if dialog.exec() == QDialog.Accepted:
            loading_dialog = LoadingDialog(self)
            loading_dialog.exec()
            
            self.config['Settings']['license_status'] = hashlib.sha256("ACTIVATED".encode()).hexdigest()
            self.config['Settings']['company_name'] = dialog.company_name
            self.config['Settings']['pan_number'] = dialog.pan_number
            self.company_name = dialog.company_name
            self.pan_number = dialog.pan_number
            try:
                with open(CONFIG_PATH, 'w') as configfile:
                    self.config.write(configfile)
            except Exception as e:
                logging.error(f"Failed to save config: {e}")
                self.create_message_box("Error", f"Failed to save license config: {e}", QMessageBox.Critical).exec()
                return False
            self.update_activation_status()
            return True
        return False

    def get_product_names(self):
        try:
            self.cursor.execute("SELECT name FROM products")
            return [row[0] for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Failed to fetch product names: {e}")
            return []

    def setup_databases(self):
        self.db = QSqlDatabase.addDatabase("QSQLITE", "products")
        self.db.setDatabaseName(DB_PATH)
        if not self.db.open():
            raise Exception("Could not open products database!")
        
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        
        # Main tables
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS products
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL UNIQUE,
                            type TEXT NOT NULL,
                            buy_price REAL NOT NULL,
                            sell_price REAL NOT NULL,
                            last_updated TEXT,
                            stock INTEGER DEFAULT 0)''')
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS stock_history
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            product_id INTEGER,
                            date TEXT,
                            quantity_change INTEGER,
                            reason TEXT,
                            FOREIGN KEY(product_id) REFERENCES products(id))''')
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS invoices
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            invoice_number TEXT NOT NULL UNIQUE,
                            date TEXT NOT NULL,
                            customer_name TEXT NOT NULL,
                            total REAL NOT NULL,
                            vat REAL NOT NULL,
                            grand_total REAL NOT NULL,
                            timestamp TEXT NOT NULL,
                            sale_id INTEGER,
                            FOREIGN KEY(sale_id) REFERENCES daily_accessories_sales(id))''')
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS invoice_items
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            invoice_id INTEGER,
                            product_id INTEGER,
                            quantity INTEGER NOT NULL,
                            unit_price REAL NOT NULL,
                            discount REAL DEFAULT 0,
                            total REAL NOT NULL,
                            FOREIGN KEY(invoice_id) REFERENCES invoices(id),
                            FOREIGN KEY(product_id) REFERENCES products(id))''')
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS qr_payments
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL,
                            image_path TEXT NOT NULL)''')

        # Daily log tables (now persistent, no daily reset)
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS daily_accessories_sales
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            date TEXT, 
                            item TEXT, 
                            quantity INTEGER, 
                            sale_price REAL, 
                            discount REAL DEFAULT 0,
                            total REAL, 
                            product_id INTEGER)''')
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS bank_transactions
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            date TEXT, 
                            amount REAL, 
                            description TEXT,
                            type TEXT CHECK(type IN ('expense', 'profit')))''')
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS expenses
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            date TEXT, 
                            description TEXT, 
                            amount REAL)''')
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS damaged_products
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            date TEXT,
                            product_name TEXT,
                            quantity INTEGER,
                            product_id INTEGER,
                            replaced INTEGER DEFAULT 0,
                            FOREIGN KEY(product_id) REFERENCES products(id))''')

        # Indexes for performance
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products (name)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_history_product_id ON stock_history (product_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices (date)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON daily_accessories_sales (date)")
        self.conn.commit()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        central_widget.setStyleSheet(f"background-color: {PRIMARY_BG};")

        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        toolbar.setStyleSheet(f"""
            QToolBar {{ 
                background-color: {SECONDARY_BG}; 
                padding: 8px; 
                border-bottom: 1px solid {BORDER_COLOR}; 
            }}
            QToolButton {{ 
                color: {TEXT_COLOR}; 
                padding: 6px; 
                font-family: Segoe UI; 
                font-size: 14px; 
                font-weight: bold;
            }}
            QToolButton:hover {{ 
                background-color: {HOVER_COLOR}; 
                color: white; 
                border-radius: 4px;
            }}
        """)
        actions = [
            ("Export CSV", self.export_to_csv),
            ("Import CSV", self.import_from_csv),
            ("Stock History", self.show_stock_history),
            ("Backup Data", self.backup_data),
            ("Restore Data", self.restore_data),
            ("Reconcile Stock", self.reconcile_stock),
            ("About", self.show_about)
        ]
        for name, slot in actions:
            action = QAction(name, self)
            action.triggered.connect(slot)
            toolbar.addAction(action)

        toolbar.addSeparator()
        self.update_activation_status()
        toolbar.addWidget(self.activation_label)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ 
                border: none; 
                background: {SECONDARY_BG}; 
                border-radius: 8px;
            }}
            QTabBar::tab {{ 
                background: {BORDER_COLOR}; 
                color: {TEXT_COLOR}; 
                padding: 12px 20px; 
                border-top-left-radius: 8px; 
                border-top-right-radius: 8px; 
                font-family: Segoe UI; 
                font-size: 14px; 
                font-weight: bold;
            }}
            QTabBar::tab:selected {{ 
                background: {ACCENT_COLOR}; 
                color: white; 
            }}
            QTabBar::tab:hover:!selected {{ 
                background: {HOVER_COLOR}; 
                color: white; 
            }}
        """)
        main_layout.addWidget(self.tabs)

        self.setup_dashboard_tab()
        self.setup_products_tab()
        self.setup_log_tab()
        self.setup_invoicing_tab()
        self.setup_qr_payment_tab()

        self.statusBar = QStatusBar()
        self.statusBar.setStyleSheet(f"QStatusBar {{ background-color: {SECONDARY_BG}; color: {TEXT_COLOR}; padding: 5px; font-family: Segoe UI; font-size: 12px; font-weight: bold; border-top: 1px solid {BORDER_COLOR}; }}")
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready", 5000)

    def setup_dashboard_tab(self):
        self.dashboard_tab = Dashboard(DB_PATH, DB_PATH)  # Use same DB for dashboard
        self.tabs.addTab(self.dashboard_tab, "Dashboard")

    def update_activation_status(self):
        if self.is_licensed():
            self.activation_label.setText(f"Activated - PAN: {self.pan_number}")
            self.activation_label.setStyleSheet(f"color: {PROFIT_COLOR}; font-family: Segoe UI; font-size: 16px; font-weight: bold; padding: 6px;")
        else:
            self.activation_label.setText("Not Activated")
            self.activation_label.setStyleSheet(f"color: {DELETE_COLOR}; font-family: Segoe UI; font-size: 16px; font-weight: bold; padding: 6px;")

    def setup_products_tab(self):
        products_tab = QWidget()
        products_layout = QVBoxLayout(products_tab)
        products_layout.setSpacing(15)

        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_widget.setStyleSheet(f"background-color: {SECONDARY_BG}; padding: 15px; border-radius: 8px;")
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter product name")
        
        product_types = [
    ("", ""),
    ("Cables & Connectors", [
        "Type C to Lightning", "Type C to Type C", "MicroUSB", "Type C", "Lightning Cable", 
        "HDMI Cable", "USB Hub", "SATA Cable", "Power Cable Laptop", "Power Cable Desktop",
        "Ethernet Cable", "VGA Cable", "DisplayPort Cable", "USB to Ethernet Adapter", 
        "Audio Aux Cable", "Thunderbolt Cable", "USB Extension Cable", "DVI Cable", 
        "Coaxial Cable", "USB-C to HDMI Adapter", "Optical Audio Cable", "Magsafe Cable", 
        "RCA Cable", "FireWire Cable"
    ]),
    ("Chargers", [
        "Charger Type C", "Charger Type V8", "Charger Type Lightning", "Type C", 
        "Charging Dock", "Charging Dock PD", "Car Charger", "Laptop Charger",
        "Wireless Charger", "Solar Charger", "Fast Charger USB-A", "Wall Charger Multi-Port", 
        "Portable Charger Adapter", "USB-C PD Charger", "GaN Charger", "Travel Charger", 
        "Desktop Charging Station", "Magnetic Charger", "Bike Charger", "Power Inverter"
    ]),
    ("Audio Devices", [
        "Earphone 3.5mm", "Earphone Type C", "Earphone Lightning", "Speaker", 
        "HeadPhone", "AirPods", "Bluetooth Speaker", "Wireless Earbuds", 
        "Noise-Canceling Headphones", "Gaming Headset", "Soundbar", "Microphone",
        "Studio Monitor Speakers", "Bone Conduction Headphones", "Portable MP3 Player", 
        "Karaoke Microphone", "Audio Receiver", "Over-Ear Headphones", "In-Ear Monitors"
    ]),
    ("Peripherals", [
        "Mouse", "Keyboard", "Pendrive", "Memory Card", "MultiPlug", 
        "Webcam", "External Hard Drive", "USB Flash Drive", "Card Reader", 
        "Gaming Controller", "Mouse Pad", "Keyboard Wrist Rest", "Drawing Tablet", 
        "USB Docking Station", "Printer", "Scanner", "Trackball Mouse", 
        "Mechanical Keyboard", "Portable SSD", "Joystick"
    ]),
    ("Mobile Accessories", [
        "Mobile Holder", "Phone Holder", "Smart Watch", "PowerBank", 
        "Phone Case", "Screen Protector", "Selfie Stick", "Lens Attachment", 
        "Smartwatch Bands", "Pop Socket", "Wireless Charging Pad", "Car Phone Mount", 
        "Ring Light", "Phone Grip Strap", "VR Headset", "Stylus Pen", "Phone Cooling Pad", 
        "Waterproof Phone Pouch", "Anti-Slip Pad"
    ]),
    ("Phones", [
        "Android Phone", "Iphone", "Keypad Phone", "Foldable Phone", 
        "Budget Smartphone", "Flagship Smartphone", "Rugged Phone", "Gaming Phone", 
        "Satellite Phone", "Senior Phone", "Dual-SIM Phone", "Refurbished Phone"
    ]),
    ("Computer Components", [
        "SDD", "HDD", "RAM", "Router", "Graphics Card", "Motherboard", 
        "CPU Cooler", "Power Supply Unit", "Network Switch", "Wi-Fi Adapter", 
        "Optical Drive", "CPU", "Case Fan", "Liquid Cooling System", "Thermal Paste", 
        "UPS (Uninterruptible Power Supply)", "Network Extender", "Sound Card", 
        "NVMe SSD", "PCIe Riser Cable", "USB Expansion Card"
    ]),
    ("Grooming & Others", [
        "Hair Trimmer", "Beard Trimmer", "Electric Shaver", "Hair Dryer", 
        "Nail Clipper Set", "Massage Gun", "Smart Scale", "Electric Toothbrush",
        "Hair Straightener", "Curling Iron", "Facial Steamer", "Manicure Kit", 
        "Foot Massager", "Nose Hair Trimmer", "Epilator", "Blood Pressure Monitor", 
        "Digital Thermometer", "Aromatherapy Diffuser"
    ])
]
        
        self.type_selector = CategorySelector(product_types)
        self.buy_price_input = QLineEdit()
        self.buy_price_input.setPlaceholderText("e.g., 10.50")
        self.sell_price_input = QLineEdit()
        self.sell_price_input.setPlaceholderText("e.g., 15.00")
        self.stock_input = QLineEdit()
        self.stock_input.setPlaceholderText("Stock Quantity")

        inputs = [
            ("Name:", self.name_input), ("Type:", self.type_selector),
            ("Buy Price:", self.buy_price_input), ("Sell Price:", self.sell_price_input),
            ("Stock:", self.stock_input)
        ]
        for label, widget in inputs:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"font-weight: bold; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
            input_layout.addWidget(lbl)
            if widget != self.type_selector:
                widget.setStyleSheet(f"padding: 8px; border: 1px solid {BORDER_COLOR}; border-radius: 6px; background-color: {PRIMARY_BG}; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
            input_layout.addWidget(widget)

        products_layout.addWidget(input_widget)

        button_layout = QHBoxLayout()
        buttons = [
            ("Add Product", self.add_product, ACCENT_COLOR),
            ("Update Product", self.update_product, UPDATE_COLOR),
            ("Delete Product", self.delete_product, DELETE_COLOR),
            ("Clear Fields", self.clear_fields, ACCENT_COLOR)
        ]
        for text, slot, color in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            btn.setStyleSheet(f"background-color: {color}; color: white; padding: 10px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none;")
            btn.setCursor(Qt.PointingHandCursor)
            button_layout.addWidget(btn)
        products_layout.addLayout(button_layout)

        search_widget = QWidget()
        search_layout = QVBoxLayout(search_widget)
        search_widget.setStyleSheet(f"background-color: {SECONDARY_BG}; padding: 15px; border-radius: 8px;")
        
        basic_search = QHBoxLayout()
        self.search_name_input = QLineEdit()
        self.search_name_input.setPlaceholderText("Search by name (regex supported)")
        self.search_name_input.textChanged.connect(self.debounce_search)
        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems(["All Types"] + [t for _, ts in product_types[1:] for t in ts])
        self.search_type_combo.currentTextChanged.connect(self.debounce_search)
        for widget in [self.search_name_input, self.search_type_combo]:
            widget.setStyleSheet(f"padding: 8px; border: 1px solid {BORDER_COLOR}; border-radius: 6px; background-color: {PRIMARY_BG}; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
        basic_search.addWidget(QLabel("Search:", styleSheet=f"font-weight: bold; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;"))
        basic_search.addWidget(self.search_name_input)
        basic_search.addWidget(QLabel("Type:", styleSheet=f"font-weight: bold; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;"))
        basic_search.addWidget(self.search_type_combo)
        search_layout.addLayout(basic_search)

        advanced_search = QFormLayout()
        self.min_buy_input = QLineEdit()
        self.max_buy_input = QLineEdit()
        self.min_sell_input = QLineEdit()
        self.max_sell_input = QLineEdit()
        self.updated_after_input = QLineEdit()
        self.stock_min_input = QLineEdit()
        self.stock_max_input = QLineEdit()
        
        advanced_inputs = [
            ("Min Buy:", self.min_buy_input), ("Max Buy:", self.max_buy_input),
            ("Min Sell:", self.min_sell_input), ("Max Sell:", self.max_sell_input),
            ("Updated After:", self.updated_after_input),
            ("Min Stock:", self.stock_min_input), ("Max Stock:", self.stock_max_input)
        ]
        for label, widget in advanced_inputs:
            widget.textChanged.connect(self.debounce_search)
            widget.setStyleSheet(f"padding: 8px; border: 1px solid {BORDER_COLOR}; border-radius: 6px; background-color: {PRIMARY_BG}; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold; max-width: 100px;")
            advanced_search.addRow(QLabel(label, styleSheet=f"color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;"), widget)

        self.advanced_search_toggle = QCheckBox("Advanced Filters")
        self.advanced_search_toggle.setStyleSheet(f"color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
        self.advanced_search_toggle.stateChanged.connect(self.toggle_advanced_search)
        search_layout.addWidget(self.advanced_search_toggle)
        self.advanced_search_widget = QWidget()
        self.advanced_search_widget.setLayout(advanced_search)
        self.advanced_search_widget.setVisible(False)
        search_layout.addWidget(self.advanced_search_widget)

        products_layout.addWidget(search_widget)

        self.table_model = QSqlTableModel(self, self.db)
        self.table_model.setTable("products")
        self.table_model.setEditStrategy(QSqlTableModel.OnManualSubmit)

        self.filter_model = AdvancedProductFilterModel(self)
        self.filter_model.setSourceModel(self.table_model)

        self.table = QTableView()
        self.table.setModel(self.filter_model)
        self.table.setStyleSheet(f"QTableView {{ background-color: {SECONDARY_BG}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 13px; font-weight: bold; gridline-color: {BORDER_COLOR}; }} QTableView::item:selected {{ background-color: {HOVER_COLOR}; color: white; }} QHeaderView::section {{ background-color: {HEADER_BG}; color: white; padding: 8px; border: none; font-family: Segoe UI; font-size: 14px; font-weight: bold; }}")
        self.table.setItemDelegate(HighlightDelegate(self.table))
        self.table.clicked.connect(self.on_table_select)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for col, header in enumerate(["Name", "Type", "Buy Price", "Sell Price", "Last Updated", "Stock"], start=1):
            self.table_model.setHeaderData(col, Qt.Horizontal, header)
        
        self.table.setColumnHidden(0, True)
        self.table.verticalHeader().setVisible(False)
        products_layout.addWidget(self.table)
        self.tabs.addTab(products_tab, "Products")

    def setup_log_tab(self):
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.log_tabs = QTabWidget()
        log_layout.addWidget(self.log_tabs)
        today = self.current_date

        sales_tab = QWidget()
        sales_layout = QVBoxLayout(sales_tab)
        sales_layout.addWidget(QLabel("Sales", styleSheet=f"font-weight: bold; font-size: 16px; color: {TEXT_COLOR}; font-family: Segoe UI; font-weight: bold;"))
        
        self.sales_table = QTableView()
        self.sales_model = QSqlTableModel(self, self.db)
        self.sales_model.setTable("daily_accessories_sales")
        self.sales_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.sales_table.setModel(self.sales_model)
        self.sales_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sales_table.clicked.connect(self.on_sales_select)
        self.sales_table.setStyleSheet(f"QTableView {{ background-color: {SECONDARY_BG}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 13px; font-weight: bold; gridline-color: {BORDER_COLOR}; }} QTableView::item:selected {{ background-color: {HOVER_COLOR}; color: white; }} QHeaderView::section {{ background-color: {HEADER_BG}; color: white; padding: 8px; border: none; font-family: Segoe UI; font-size: 14px; font-weight: bold; }}")
        headers = ["Date", "Item", "Quantity", "Sale Price", "Discount", "Total", "Product ID"]
        for col, header in enumerate(headers, start=1):
            self.sales_model.setHeaderData(col, Qt.Horizontal, header)
        self.sales_table.setColumnHidden(0, True)
        self.sales_table.setColumnHidden(6, True)
        self.sales_table.verticalHeader().setVisible(False)
        sales_layout.addWidget(self.sales_table)
        
        sales_input_widget = QWidget()
        sales_input_layout = QHBoxLayout(sales_input_widget)
        sales_input_widget.setStyleSheet(f"background-color: {SECONDARY_BG}; padding: 10px; border-radius: 8px;")
        
        self.sales_date = QLineEdit(today)
        self.sales_item = QLineEdit()
        self.sales_completer = QCompleter(self.product_names, self.sales_item)
        self.sales_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.sales_completer.setFilterMode(Qt.MatchContains)
        self.sales_item.setCompleter(self.sales_completer)
        self.sales_quantity = QLineEdit()
        self.sales_price = QLineEdit()
        self.sales_discount = QLineEdit()
        self.sales_discount.setPlaceholderText("Discount % (0-100)")
        
        inputs = [
            ("Date:", self.sales_date), 
            ("Item:", self.sales_item), 
            ("Qty:", self.sales_quantity), 
            ("Price:", self.sales_price),
            ("Disc %:", self.sales_discount)
        ]
        for label, widget in inputs:
            widget.setStyleSheet(f"padding: 8px; border: 1px solid {BORDER_COLOR}; border-radius: 6px; background-color: {PRIMARY_BG}; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
            sales_input_layout.addWidget(QLabel(label, styleSheet=f"color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;"))
            sales_input_layout.addWidget(widget)
        
        sales_add_btn = QPushButton("Add Sale")
        sales_add_btn.clicked.connect(self.add_sale)
        sales_edit_btn = QPushButton("Edit Sale")
        sales_edit_btn.clicked.connect(self.edit_sale)
        sales_del_btn = QPushButton("Delete Sale")
        sales_del_btn.clicked.connect(self.delete_sale)
        for btn, color in [(sales_add_btn, ACCENT_COLOR), (sales_edit_btn, UPDATE_COLOR), (sales_del_btn, DELETE_COLOR)]:
            btn.setStyleSheet(f"background-color: {color}; color: white; padding: 10px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none;")
            btn.setCursor(Qt.PointingHandCursor)
            sales_input_layout.addWidget(btn)
        
        sales_layout.addWidget(sales_input_widget)
        self.sales_total = QLabel("Total Sales: NPR 0.00", styleSheet=f"color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
        sales_layout.addWidget(self.sales_total)
        self.log_tabs.addTab(sales_tab, "Sales")

        bank_tab = QWidget()
        bank_layout = QVBoxLayout(bank_tab)
        bank_layout.addWidget(QLabel("Bank Transactions", styleSheet=f"font-weight: bold; font-size: 16px; color: {TEXT_COLOR}; font-family: Segoe UI; font-weight: bold;"))
        
        self.bank_table = QTableView()
        self.bank_model = QSqlTableModel(self, self.db)
        self.bank_model.setTable("bank_transactions")
        self.bank_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.bank_table.setModel(self.bank_model)
        self.bank_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.bank_table.clicked.connect(self.on_bank_select)
        self.bank_table.setStyleSheet(f"QTableView {{ background-color: {SECONDARY_BG}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 13px; font-weight: bold; gridline-color: {BORDER_COLOR}; }} QTableView::item:selected {{ background-color: {HOVER_COLOR}; color: white; }} QHeaderView::section {{ background-color: {HEADER_BG}; color: white; padding: 8px; border: none; font-family: Segoe UI; font-size: 14px; font-weight: bold; }}")
        bank_headers = ["Date", "Amount", "Description", "Type"]
        for col, header in enumerate(bank_headers, start=1):
            self.bank_model.setHeaderData(col, Qt.Horizontal, header)
        self.bank_table.setColumnHidden(0, True)
        self.bank_table.verticalHeader().setVisible(False)
        bank_layout.addWidget(self.bank_table)
        
        bank_input_layout = QHBoxLayout()
        self.bank_date = QLineEdit(today)
        self.bank_amount = QLineEdit()
        self.bank_desc = QLineEdit()
        inputs = [("Date:", self.bank_date), ("Amount:", self.bank_amount), ("Desc:", self.bank_desc)]
        for label, widget in inputs:
            widget.setStyleSheet(f"padding: 8px; border: 1px solid {BORDER_COLOR}; border-radius: 6px; background-color: {PRIMARY_BG}; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
            bank_input_layout.addWidget(QLabel(label, styleSheet=f"color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;"))
            bank_input_layout.addWidget(widget)
        
        bank_expense_btn = QPushButton("Add Expense")
        bank_expense_btn.clicked.connect(lambda: self.add_bank('expense'))
        bank_profit_btn = QPushButton("Add Profit")
        bank_profit_btn.clicked.connect(lambda: self.add_bank('profit'))
        bank_edit_btn = QPushButton("Edit")
        bank_edit_btn.clicked.connect(self.edit_bank)
        bank_del_btn = QPushButton("Delete")
        bank_del_btn.clicked.connect(self.delete_bank)
        
        for btn, color in [(bank_expense_btn, DELETE_COLOR), (bank_profit_btn, PROFIT_COLOR), (bank_edit_btn, UPDATE_COLOR), (bank_del_btn, DELETE_COLOR)]:
            btn.setStyleSheet(f"background-color: {color}; color: white; padding: 10px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none;")
            btn.setCursor(Qt.PointingHandCursor)
            bank_input_layout.addWidget(btn)
        
        bank_layout.addLayout(bank_input_layout)
        self.bank_total = QLabel("Total Bank: NPR 0.00", styleSheet=f"color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
        bank_layout.addWidget(self.bank_total)
        self.log_tabs.addTab(bank_tab, "Bank")

        expenses_tab = QWidget()
        expenses_layout = QVBoxLayout(expenses_tab)
        expenses_layout.addWidget(QLabel("Expenses", styleSheet=f"font-weight: bold; font-size: 16px; color: {TEXT_COLOR}; font-family: Segoe UI; font-weight: bold;"))
        self.expenses_table = QTableView()
        self.expenses_model = QSqlTableModel(self, self.db)
        self.expenses_model.setTable("expenses")
        self.expenses_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.expenses_table.setModel(self.expenses_model)
        self.expenses_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.expenses_table.clicked.connect(self.on_expenses_select)
        self.expenses_table.setStyleSheet(f"QTableView {{ background-color: {SECONDARY_BG}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 13px; font-weight: bold; gridline-color: {BORDER_COLOR}; }} QTableView::item:selected {{ background-color: {HOVER_COLOR}; color: white; }} QHeaderView::section {{ background-color: {HEADER_BG}; color: white; padding: 8px; border: none; font-family: Segoe UI; font-size: 14px; font-weight: bold; }}")
        for col, header in enumerate(["Date", "Description", "Amount"], start=1):
            self.expenses_model.setHeaderData(col, Qt.Horizontal, header)
        self.expenses_table.setColumnHidden(0, True)
        self.expenses_table.verticalHeader().setVisible(False)
        expenses_layout.addWidget(self.expenses_table)

        expenses_input_layout = QHBoxLayout()
        self.expenses_date = QLineEdit(today)
        self.expenses_desc = QLineEdit()
        self.expenses_amount = QLineEdit()
        for label, widget in [("Date:", self.expenses_date), ("Desc:", self.expenses_desc), ("Amount:", self.expenses_amount)]:
            widget.setStyleSheet(f"padding: 8px; border: 1px solid {BORDER_COLOR}; border-radius: 6px; background-color: {PRIMARY_BG}; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
            expenses_input_layout.addWidget(QLabel(label, styleSheet=f"color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;"))
            expenses_input_layout.addWidget(widget)

        expenses_add_btn = QPushButton("Add Expense")
        expenses_add_btn.clicked.connect(self.add_expense)
        expenses_edit_btn = QPushButton("Edit")
        expenses_edit_btn.clicked.connect(self.edit_expense)
        expenses_del_btn = QPushButton("Delete")
        expenses_del_btn.clicked.connect(self.delete_expense)
        for btn, color in [(expenses_add_btn, ACCENT_COLOR), (expenses_edit_btn, UPDATE_COLOR), (expenses_del_btn, DELETE_COLOR)]:
            btn.setStyleSheet(f"background-color: {color}; color: white; padding: 10px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none;")
            btn.setCursor(Qt.PointingHandCursor)
            expenses_input_layout.addWidget(btn)
        expenses_layout.addLayout(expenses_input_layout)
        self.expenses_total = QLabel("Total Expenses: NPR 0.00", styleSheet=f"color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
        expenses_layout.addWidget(self.expenses_total)
        self.log_tabs.addTab(expenses_tab, "Expenses")

        damage_tab = QWidget()
        damage_layout = QVBoxLayout(damage_tab)
        damage_layout.addWidget(QLabel("Damaged Products", styleSheet=f"font-weight: bold; font-size: 16px; color: {TEXT_COLOR}; font-family: Segoe UI; font-weight: bold;"))
        
        self.damage_table = QTableView()
        self.damage_model = QSqlTableModel(self, self.db)
        self.damage_model.setTable("damaged_products")
        self.damage_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.damage_table.setModel(self.damage_model)
        self.damage_table.setItemDelegate(DamageStatusDelegate(self.damage_table))
        self.damage_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.damage_table.clicked.connect(self.on_damage_select)
        self.damage_table.setStyleSheet(f"QTableView {{ background-color: {SECONDARY_BG}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 13px; font-weight: bold; gridline-color: {BORDER_COLOR}; }} QTableView::item:selected {{ background-color: {HOVER_COLOR}; color: white; }} QHeaderView::section {{ background-color: {HEADER_BG}; color: white; padding: 8px; border: none; font-family: Segoe UI; font-size: 14px; font-weight: bold; }}")
        
        damage_headers = ["ID", "Date", "Product Name", "Quantity", "Product ID", "Replaced"]
        for col, header in enumerate(damage_headers):
            self.damage_model.setHeaderData(col, Qt.Horizontal, header)
        
        self.damage_table.setColumnHidden(0, True)
        self.damage_table.setColumnHidden(4, True)
        self.damage_table.verticalHeader().setVisible(False)
        damage_layout.addWidget(self.damage_table)
        
        damage_input_widget = QWidget()
        damage_input_layout = QHBoxLayout(damage_input_widget)
        damage_input_widget.setStyleSheet(f"background-color: {SECONDARY_BG}; padding: 10px; border-radius: 8px;")
        
        self.damage_date = QLineEdit(today)
        self.damage_product = QLineEdit()
        self.damage_completer = QCompleter(self.product_names, self.damage_product)
        self.damage_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.damage_completer.setFilterMode(Qt.MatchContains)
        self.damage_product.setCompleter(self.damage_completer)
        self.damage_quantity = QLineEdit()
        
        damage_inputs = [
            ("Date:", self.damage_date),
            ("Product:", self.damage_product),
            ("Qty:", self.damage_quantity)
        ]
        for label, widget in damage_inputs:
            widget.setStyleSheet(f"padding: 8px; border: 1px solid {BORDER_COLOR}; border-radius: 6px; background-color: {PRIMARY_BG}; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
            damage_input_layout.addWidget(QLabel(label, styleSheet=f"color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;"))
            damage_input_layout.addWidget(widget)
        
        damage_add_btn = QPushButton("Add Damage")
        damage_add_btn.clicked.connect(self.add_damage)
        damage_replace_btn = QPushButton("Replace")
        damage_replace_btn.clicked.connect(self.replace_damage)
        damage_del_btn = QPushButton("Delete")
        damage_del_btn.clicked.connect(self.delete_damage)
        
        for btn, color in [(damage_add_btn, DELETE_COLOR), (damage_replace_btn, REPLACE_COLOR), (damage_del_btn, DELETE_COLOR)]:
            btn.setStyleSheet(f"background-color: {color}; color: white; padding: 10px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none;")
            btn.setCursor(Qt.PointingHandCursor)
            damage_input_layout.addWidget(btn)
        
        damage_layout.addWidget(damage_input_widget)
        self.damage_total = QLabel("Total Damaged: 0", styleSheet=f"color: {DELETE_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
        damage_layout.addWidget(self.damage_total)
        self.log_tabs.addTab(damage_tab, "Damage")

        self.tabs.addTab(log_tab, "Daily Log")

    def setup_invoicing_tab(self):
        invoicing_tab = QWidget()
        invoicing_layout = QVBoxLayout(invoicing_tab)
        invoicing_layout.addWidget(QLabel("Invoicing", styleSheet=f"font-weight: bold; font-size: 16px; color: {TEXT_COLOR}; font-family: Segoe UI; font-weight: bold;"))

        invoice_input_widget = QWidget()
        invoice_input_layout = QHBoxLayout(invoice_input_widget)
        invoice_input_widget.setStyleSheet(f"background-color: {SECONDARY_BG}; padding: 10px; border-radius: 8px;")

        self.invoice_date = QLineEdit(self.current_date)
        self.customer_name = QLineEdit()
        self.customer_name.setPlaceholderText("Customer Name")
        self.product_selector = QComboBox()
        self.product_selector.addItems(self.product_names)
        self.invoice_quantity = QLineEdit()
        self.invoice_quantity.setPlaceholderText("Quantity")
        self.invoice_discount = QLineEdit()
        self.invoice_discount.setPlaceholderText("Discount % (0-100)")

        self.invoice_source = QComboBox()
        self.invoice_source.addItems(["From Stock", "From Sale"])
        self.invoice_source.currentIndexChanged.connect(self.toggle_sale_selector)

        self.sale_selector = QComboBox()
        self.refresh_sale_selector()
        self.sale_selector.setEnabled(False)
        self.sale_selector.currentIndexChanged.connect(self.on_sale_select)

        inputs = [
            ("Date:", self.invoice_date),
            ("Customer:", self.customer_name),
            ("Source:", self.invoice_source),
            ("Sale:", self.sale_selector),
            ("Product:", self.product_selector),
            ("Qty:", self.invoice_quantity),
            ("Disc %:", self.invoice_discount)
        ]
        for label, widget in inputs:
            widget.setStyleSheet(f"padding: 8px; border: 1px solid {BORDER_COLOR}; border-radius: 6px; background-color: {PRIMARY_BG}; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
            invoice_input_layout.addWidget(QLabel(label, styleSheet=f"color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;"))
            invoice_input_layout.addWidget(widget)

        add_invoice_btn = QPushButton("Add Invoice")
        add_invoice_btn.clicked.connect(self.add_invoice)
        add_invoice_btn.setStyleSheet(f"background-color: {ACCENT_COLOR}; color: white; padding: 10px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none;")
        add_invoice_btn.setCursor(Qt.PointingHandCursor)
        invoice_input_layout.addWidget(add_invoice_btn)

        invoicing_layout.addWidget(invoice_input_widget)

        self.invoice_table = QTableView()
        self.invoice_model = QSqlTableModel(self, self.db)
        self.invoice_model.setTable("invoices")
        self.invoice_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.invoice_table.setModel(self.invoice_model)
        self.invoice_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.invoice_table.clicked.connect(self.on_invoice_select)
        self.invoice_table.setStyleSheet(f"QTableView {{ background-color: {SECONDARY_BG}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 13px; font-weight: bold; gridline-color: {BORDER_COLOR}; }} QTableView::item:selected {{ background-color: {HOVER_COLOR}; color: white; }} QHeaderView::section {{ background-color: {HEADER_BG}; color: white; padding: 8px; border: none; font-family: Segoe UI; font-size: 14px; font-weight: bold; }}")
        headers = ["Invoice Number", "Date", "Customer Name", "Total", "VAT", "Grand Total", "Timestamp", "Sale ID"]
        for col, header in enumerate(headers, start=1):
            self.invoice_model.setHeaderData(col, Qt.Horizontal, header)
        self.invoice_table.setColumnHidden(0, True)
        self.invoice_table.setColumnHidden(7, True)
        self.invoice_table.verticalHeader().setVisible(False)
        invoicing_layout.addWidget(self.invoice_table)

        invoice_actions_layout = QHBoxLayout()
        self.view_invoice_btn = QPushButton("View Invoice")
        self.view_invoice_btn.clicked.connect(self.view_invoice)
        self.delete_invoice_btn = QPushButton("Delete Invoice")
        self.delete_invoice_btn.clicked.connect(self.delete_invoice)
        for btn, color in [(self.view_invoice_btn, ACCENT_COLOR), (self.delete_invoice_btn, DELETE_COLOR)]:
            btn.setStyleSheet(f"background-color: {color}; color: white; padding: 10px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none;")
            btn.setCursor(Qt.PointingHandCursor)
            invoice_actions_layout.addWidget(btn)
        invoicing_layout.addLayout(invoice_actions_layout)

        self.tabs.addTab(invoicing_tab, "Invoicing")

    def setup_qr_payment_tab(self):
        qr_tab = QWidget()
        qr_layout = QVBoxLayout(qr_tab)
        qr_layout.addWidget(QLabel("QR Payments", styleSheet=f"font-weight: bold; font-size: 16px; color: {TEXT_COLOR}; font-family: Segoe UI; font-weight: bold;"))

        qr_input_widget = QWidget()
        qr_input_layout = QHBoxLayout(qr_input_widget)
        qr_input_widget.setStyleSheet(f"background-color: {SECONDARY_BG}; padding: 10px; border-radius: 8px;")

        self.qr_name = QLineEdit()
        self.qr_name.setPlaceholderText("Payment Name")
        self.qr_path = QLineEdit()
        self.qr_path.setPlaceholderText("QR Image Path")
        self.qr_path.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_qr)
        add_qr_btn = QPushButton("Add QR")
        add_qr_btn.clicked.connect(self.add_qr_payment)
        
        for widget in [self.qr_name, self.qr_path]:
            widget.setStyleSheet(f"padding: 8px; border: 1px solid {BORDER_COLOR}; border-radius: 6px; background-color: {PRIMARY_BG}; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 14px; font-weight: bold;")
            qr_input_layout.addWidget(widget)
        for btn, color in [(browse_btn, ACCENT_COLOR), (add_qr_btn, ACCENT_COLOR)]:
            btn.setStyleSheet(f"background-color: {color}; color: white; padding: 10px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none;")
            btn.setCursor(Qt.PointingHandCursor)
            qr_input_layout.addWidget(btn)

        qr_layout.addWidget(qr_input_widget)

        self.qr_table = QTableView()
        self.qr_model = QSqlTableModel(self, self.db)
        self.qr_model.setTable("qr_payments")
        self.qr_model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.qr_table.setModel(self.qr_model)
        self.qr_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.qr_table.clicked.connect(self.on_qr_select)
        self.qr_table.setStyleSheet(f"QTableView {{ background-color: {SECONDARY_BG}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 13px; font-weight: bold; gridline-color: {BORDER_COLOR}; }} QTableView::item:selected {{ background-color: {HOVER_COLOR}; color: white; }} QHeaderView::section {{ background-color: {HEADER_BG}; color: white; padding: 8px; border: none; font-family: Segoe UI; font-size: 14px; font-weight: bold; }}")
        for col, header in enumerate(["Name", "Image Path"], start=1):
            self.qr_model.setHeaderData(col, Qt.Horizontal, header)
        self.qr_table.setColumnHidden(0, True)
        self.qr_table.verticalHeader().setVisible(False)
        qr_layout.addWidget(self.qr_table)

        qr_actions_layout = QHBoxLayout()
        view_qr_btn = QPushButton("View QR")
        view_qr_btn.clicked.connect(self.view_qr)
        delete_qr_btn = QPushButton("Delete QR")
        delete_qr_btn.clicked.connect(self.delete_qr)
        for btn, color in [(view_qr_btn, ACCENT_COLOR), (delete_qr_btn, DELETE_COLOR)]:
            btn.setStyleSheet(f"background-color: {color}; color: white; padding: 10px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none;")
            btn.setCursor(Qt.PointingHandCursor)
            qr_actions_layout.addWidget(btn)
        qr_layout.addLayout(qr_actions_layout)

        self.tabs.addTab(qr_tab, "QR Payments")

    def add_product(self):
        data = self.get_input_data()
        if not data:
            return
        name, type_, buy_price, sell_price, stock = data
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("INSERT INTO products (name, type, buy_price, sell_price, last_updated, stock) VALUES (?, ?, ?, ?, ?, ?)",
                               (name, type_, buy_price, sell_price, timestamp, stock))
            product_id = self.cursor.lastrowid
            if stock > 0:
                self.cursor.execute("INSERT INTO stock_history (product_id, date, quantity_change, reason) VALUES (?, ?, ?, ?)",
                                   (product_id, timestamp, stock, "Initial stock"))
            self.conn.commit()
            self.product_names = self.get_product_names()
            self.sales_completer.setModel(QStringListModel(self.product_names))
            self.damage_completer.setModel(QStringListModel(self.product_names))
            self.product_selector.clear()
            self.product_selector.addItems(self.product_names)
            self.load_data()
            self.clear_fields()
            self.statusBar.showMessage(f"Product '{name}' added", 5000)
            logging.info(f"Product '{name}' added with stock {stock}")
        except sqlite3.IntegrityError:
            self.create_message_box("Error", f"Product '{name}' already exists!", QMessageBox.Warning).exec()

    def update_product(self):
        if not self.table.currentIndex().isValid():
            self.create_message_box("Error", "Select a product to update!", QMessageBox.Warning).exec()
            return
        row = self.filter_model.mapToSource(self.table.currentIndex()).row()
        product_id = self.table_model.index(row, 0).data()
        data = self.get_input_data()
        if not data:
            return
        name, type_, buy_price, sell_price, stock = data
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("SELECT stock FROM products WHERE id=?", (product_id,))
            old_stock = self.cursor.fetchone()[0]
            stock_change = stock - old_stock
            self.cursor.execute("UPDATE products SET name=?, type=?, buy_price=?, sell_price=?, last_updated=?, stock=? WHERE id=?",
                               (name, type_, buy_price, sell_price, timestamp, stock, product_id))
            if stock_change != 0:
                self.cursor.execute("INSERT INTO stock_history (product_id, date, quantity_change, reason) VALUES (?, ?, ?, ?)",
                                   (product_id, timestamp, stock_change, "Stock updated"))
            self.conn.commit()
            self.product_names = self.get_product_names()
            self.sales_completer.setModel(QStringListModel(self.product_names))
            self.damage_completer.setModel(QStringListModel(self.product_names))
            self.product_selector.clear()
            self.product_selector.addItems(self.product_names)
            self.load_data()
            self.clear_fields()
            logging.info(f"Product '{name}' updated with stock change {stock_change}")
        except sqlite3.IntegrityError:
            self.create_message_box("Error", f"Product '{name}' already exists!", QMessageBox.Warning).exec()

    def delete_product(self):
        if not self.table.currentIndex().isValid():
            self.create_message_box("Error", "Select a product to delete!", QMessageBox.Warning).exec()
            return
        row = self.filter_model.mapToSource(self.table.currentIndex()).row()
        product_id = self.table_model.index(row, 0).data()
        name = self.table_model.index(row, 1).data()
        reply = self.create_message_box("Confirm", f"Delete '{name}'?", QMessageBox.Question, QMessageBox.Yes | QMessageBox.No)
        if reply.exec() == QMessageBox.Yes:
            self.cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
            self.cursor.execute("DELETE FROM stock_history WHERE product_id=?", (product_id,))
            self.conn.commit()
            self.product_names = self.get_product_names()
            self.sales_completer.setModel(QStringListModel(self.product_names))
            self.damage_completer.setModel(QStringListModel(self.product_names))
            self.product_selector.clear()
            self.product_selector.addItems(self.product_names)
            self.load_data()
            self.clear_fields()
            self.statusBar.showMessage(f"Product '{name}' deleted", 5000)
            logging.info(f"Product '{name}' deleted")

    def reconcile_stock(self):
        self.cursor.execute("SELECT id, name, stock FROM products")
        products = self.cursor.fetchall()
        for prod_id, name, stock in products:
            self.cursor.execute("SELECT SUM(quantity_change) FROM stock_history WHERE product_id=?", (prod_id,))
            total_change = self.cursor.fetchone()[0] or 0
            if total_change != stock:
                discrepancy = stock - total_change
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.cursor.execute("INSERT INTO stock_history (product_id, date, quantity_change, reason) VALUES (?, ?, ?, ?)",
                                   (prod_id, timestamp, discrepancy, "Stock reconciliation"))
                logging.info(f"Stock reconciled for '{name}': adjusted by {discrepancy}")
        self.conn.commit()
        self.load_data()
        self.statusBar.showMessage("Stock reconciled", 5000)

    def update_stock(self, product_id, quantity_change, reason):
        try:
            self.cursor.execute("SELECT stock FROM products WHERE id=?", (product_id,))
            current_stock = self.cursor.fetchone()[0]
            new_stock = current_stock + quantity_change
            if new_stock < 0:
                self.create_message_box("Error", f"Stock cannot go below 0! Current: {current_stock}", QMessageBox.Warning).exec()
                return None
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("UPDATE products SET stock=?, last_updated=? WHERE id=?", (new_stock, timestamp, product_id))
            self.cursor.execute("INSERT INTO stock_history (product_id, date, quantity_change, reason) VALUES (?, ?, ?, ?)",
                               (product_id, timestamp, quantity_change, reason))
            self.conn.commit()
            if new_stock <= 5:
                self.cursor.execute("SELECT name FROM products WHERE id=?", (product_id,))
                name = self.cursor.fetchone()[0]
                self.low_stock_signal.emit(name, new_stock)
            return new_stock
        except sqlite3.Error as e:
            logging.error(f"Failed to update stock: {e}")
            self.create_message_box("Error", f"Failed to update stock: {e}", QMessageBox.Critical).exec()
            return None

    def show_low_stock_alert(self, name, stock):
        self.create_message_box("Low Stock Alert", f"'{name}' stock is low: {stock} remaining!", QMessageBox.Warning).exec()

    def on_table_select(self, index):
        row = self.filter_model.mapToSource(index).row()
        self.id_input.setText(str(self.table_model.index(row, 0).data()))
        self.name_input.setText(str(self.table_model.index(row, 1).data()))
        self.type_selector.setCurrentText(str(self.table_model.index(row, 2).data()))
        self.buy_price_input.setText(str(self.table_model.index(row, 3).data()))
        self.sell_price_input.setText(str(self.table_model.index(row, 4).data()))
        self.stock_input.setText(str(self.table_model.index(row, 6).data()))

    def on_sales_select(self, index):
        row = index.row()
        self.sales_date.setText(str(self.sales_model.index(row, 1).data()))
        self.sales_item.setText(str(self.sales_model.index(row, 2).data()))
        self.sales_quantity.setText(str(self.sales_model.index(row, 3).data()))
        self.sales_price.setText(str(self.sales_model.index(row, 4).data()))
        self.sales_discount.setText(str(self.sales_model.index(row, 5).data()))

    def add_sale(self):
        date, item, qty, price, discount = self.sales_date.text(), self.sales_item.text(), self.sales_quantity.text(), self.sales_price.text(), self.sales_discount.text() or "0"
        if not all([date, item, qty, price]):
            self.create_message_box("Error", "All fields except discount required!", QMessageBox.Warning).exec()
            return
        
        try:
            datetime.strptime(date, "%Y-%m-%d")
            qty = int(qty)
            price = float(price)
            discount = float(discount)
            if qty <= 0 or price < 0:
                raise ValueError("Quantity must be positive, price non-negative!")
            if discount < 0 or discount > 100:
                raise ValueError("Discount must be between 0 and 100%!")
            
            subtotal = qty * price
            discount_amount = subtotal * (discount / 100)
            total = subtotal - discount_amount
            
            self.cursor.execute("SELECT id, stock FROM products WHERE name = ?", (item,))
            result = self.cursor.fetchone()
            if not result:
                raise ValueError(f"Product '{item}' not found!")
            prod_id, current_stock = result
            if current_stock < qty:
                raise ValueError(f"Insufficient stock: {current_stock} available!")

            new_stock = self.update_stock(prod_id, -qty, f"Sale of {qty} units with {discount}% discount")
            if new_stock is None:
                return

            self.cursor.execute("INSERT INTO daily_accessories_sales (date, item, quantity, sale_price, discount, total, product_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (date, item, qty, price, discount, total, prod_id))
            self.conn.commit()
            self.refresh_sale_selector()
            self.load_data()
            self.clear_log_fields('sales')
            self.statusBar.showMessage(f"Sale of {qty} '{item}' added with {discount}% discount", 5000)
            logging.info(f"Sale of {qty} '{item}' added with {discount}% discount")
        except ValueError as e:
            self.create_message_box("Error", str(e), QMessageBox.Warning).exec()

    def edit_sale(self):
        if not self.sales_table.currentIndex().isValid():
            self.create_message_box("Error", "Select a sale to edit!", QMessageBox.Warning).exec()
            return
        row = self.sales_table.currentIndex().row()
        sale_id = self.sales_model.index(row, 0).data()
        date, item, qty, price, discount = self.sales_date.text(), self.sales_item.text(), self.sales_quantity.text(), self.sales_price.text(), self.sales_discount.text() or "0"
        
        try:
            datetime.strptime(date, "%Y-%m-%d")
            qty = int(qty)
            price = float(price)
            discount = float(discount)
            if qty <= 0 or price < 0 or discount < 0 or discount > 100:
                raise ValueError("Invalid input values!")
            
            subtotal = qty * price
            discount_amount = subtotal * (discount / 100)
            total = subtotal - discount_amount
            
            self.cursor.execute("SELECT quantity, product_id FROM daily_accessories_sales WHERE id=?", (sale_id,))
            old_qty, prod_id = self.cursor.fetchone()
            stock_change = old_qty - qty
            if stock_change != 0:
                self.update_stock(prod_id, stock_change, f"Sale edit (old: {old_qty}, new: {qty})")

            self.cursor.execute("UPDATE daily_accessories_sales SET date=?, item=?, quantity=?, sale_price=?, discount=?, total=?, product_id=? WHERE id=?",
                               (date, item, qty, price, discount, total, prod_id, sale_id))
            self.conn.commit()
            self.refresh_sale_selector()
            self.load_data()
            self.clear_log_fields('sales')
            logging.info(f"Sale '{item}' updated with {discount}% discount")
        except ValueError as e:
            self.create_message_box("Error", str(e), QMessageBox.Warning).exec()

    def delete_sale(self):
        if not self.sales_table.currentIndex().isValid():
            self.create_message_box("Error", "Select a sale to delete!", QMessageBox.Warning).exec()
            return
        row = self.sales_table.currentIndex().row()
        sale_id, item, qty, prod_id = (self.sales_model.index(row, i).data() for i in [0, 2, 3, 6])
        
        reply = self.create_message_box("Confirm", f"Delete sale of '{item}' ({qty} sold)?", QMessageBox.Question, QMessageBox.Yes | QMessageBox.No)
        if reply.exec() == QMessageBox.Yes:
            self.update_stock(prod_id, qty, f"Sale deletion ({qty} sold)")
            self.cursor.execute("DELETE FROM daily_accessories_sales WHERE id=?", (sale_id,))
            self.conn.commit()
            self.refresh_sale_selector()
            self.load_data()
            self.clear_log_fields('sales')
            self.statusBar.showMessage(f"Sale '{item}' deleted", 5000)
            logging.info(f"Sale '{item}' deleted")

    def on_bank_select(self, index):
        row = index.row()
        self.bank_date.setText(str(self.bank_model.index(row, 1).data()))
        self.bank_amount.setText(str(abs(float(self.bank_model.index(row, 2).data()))))
        self.bank_desc.setText(str(self.bank_model.index(row, 3).data()))

    def add_bank(self, transaction_type):
        date, amount, desc = self.bank_date.text(), self.bank_amount.text(), self.bank_desc.text()
        if not all([date, amount, desc]):
            self.create_message_box("Error", "All fields required!", QMessageBox.Warning).exec()
            return
        try:
            datetime.strptime(date, "%Y-%m-%d")
            amount = float(amount)
            if amount <= 0:
                raise ValueError("Amount must be positive!")
            adjusted_amount = -amount if transaction_type == 'expense' else amount
            
            self.cursor.execute("INSERT INTO bank_transactions (date, amount, description, type) VALUES (?, ?, ?, ?)",
                               (date, adjusted_amount, desc, transaction_type))
            self.conn.commit()
            self.load_data()
            self.clear_log_fields('bank')
            self.statusBar.showMessage(f"Bank {transaction_type} added", 5000)
            logging.info(f"Bank {transaction_type} '{desc}' added")
        except ValueError as e:
            self.create_message_box("Error", str(e), QMessageBox.Warning).exec()

    def edit_bank(self):
        if not self.bank_table.currentIndex().isValid():
            self.create_message_box("Error", "Select a transaction!", QMessageBox.Warning).exec()
            return
        row = self.bank_table.currentIndex().row()
        bank_id = self.bank_model.index(row, 0).data()
        date, amount, desc = self.bank_date.text(), self.bank_amount.text(), self.bank_desc.text()
        current_type = self.bank_model.index(row, 3).data()
        
        try:
            datetime.strptime(date, "%Y-%m-%d")
            amount = float(amount)
            adjusted_amount = -amount if current_type == 'expense' else amount
            self.cursor.execute("UPDATE bank_transactions SET date=?, amount=?, description=? WHERE id=?",
                               (date, adjusted_amount, desc, bank_id))
            self.conn.commit()
            self.load_data()
            self.clear_log_fields('bank')
            logging.info(f"Bank transaction '{desc}' updated")
        except ValueError:
            self.create_message_box("Error", "Invalid amount or date!", QMessageBox.Warning).exec()

    def delete_bank(self):
        if not self.bank_table.currentIndex().isValid():
            self.create_message_box("Error", "Select a transaction!", QMessageBox.Warning).exec()
            return
        row = self.bank_table.currentIndex().row()
        bank_id, desc = self.bank_model.index(row, 0).data(), self.bank_model.index(row, 3).data()  # Fixed typo: 'self.bank' to 'self.bank_model'
        reply = self.create_message_box("Confirm", f"Delete '{desc}'?", QMessageBox.Question, QMessageBox.Yes | QMessageBox.No)
        if reply.exec() == QMessageBox.Yes:
            self.cursor.execute("DELETE FROM bank_transactions WHERE id=?", (bank_id,))
            self.conn.commit()
            self.load_data()
            self.clear_log_fields('bank')
            self.statusBar.showMessage(f"Bank transaction '{desc}' deleted", 5000)
            logging.info(f"Bank transaction '{desc}' deleted")

    def on_expenses_select(self, index):
        row = index.row()
        self.expenses_date.setText(str(self.expenses_model.index(row, 1).data()))
        self.expenses_desc.setText(str(self.expenses_model.index(row, 2).data()))
        self.expenses_amount.setText(str(self.expenses_model.index(row, 3).data()))

    def add_expense(self):
        date, desc, amount = self.expenses_date.text(), self.expenses_desc.text(), self.expenses_amount.text()
        if not all([date, desc, amount]):
            self.create_message_box("Error", "All fields required!", QMessageBox.Warning).exec()
            return
        try:
            datetime.strptime(date, "%Y-%m-%d")
            amount = float(amount)
            if amount < 0:
                raise ValueError("Amount cannot be negative!")
            self.cursor.execute("INSERT INTO expenses (date, description, amount) VALUES (?, ?, ?)",
                               (date, desc, amount))
            self.conn.commit()
            self.load_data()
            self.clear_log_fields('expenses')
            self.statusBar.showMessage(f"Expense '{desc}' added", 5000)
            logging.info(f"Expense '{desc}' added")
        except ValueError as e:
            self.create_message_box("Error", str(e), QMessageBox.Warning).exec()

    def edit_expense(self):
        if not self.expenses_table.currentIndex().isValid():
            self.create_message_box("Error", "Select an expense!", QMessageBox.Warning).exec()
            return
        row = self.expenses_table.currentIndex().row()
        expense_id = self.expenses_model.index(row, 0).data()
        date, desc, amount = self.expenses_date.text(), self.expenses_desc.text(), self.expenses_amount.text()
        try:
            datetime.strptime(date, "%Y-%m-%d")
            amount = float(amount)
            self.cursor.execute("UPDATE expenses SET date=?, description=?, amount=? WHERE id=?",
                               (date, desc, amount, expense_id))
            self.conn.commit()
            self.load_data()
            self.clear_log_fields('expenses')
            logging.info(f"Expense '{desc}' updated")
        except ValueError:
            self.create_message_box("Error", "Invalid amount or date!", QMessageBox.Warning).exec()

    def delete_expense(self):
        if not self.expenses_table.currentIndex().isValid():
            self.create_message_box("Error", "Select an expense!", QMessageBox.Warning).exec()
            return
        row = self.expenses_table.currentIndex().row()
        expense_id, desc = self.expenses_model.index(row, 0).data(), self.expenses_model.index(row, 2).data()
        reply = self.create_message_box("Confirm", f"Delete '{desc}'?", QMessageBox.Question, QMessageBox.Yes | QMessageBox.No)
        if reply.exec() == QMessageBox.Yes:
            self.cursor.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
            self.conn.commit()
            self.load_data()
            self.clear_log_fields('expenses')
            logging.info(f"Expense '{desc}' deleted")

    def on_damage_select(self, index):
        row = index.row()
        self.damage_date.setText(str(self.damage_model.index(row, 1).data()))
        self.damage_product.setText(str(self.damage_model.index(row, 2).data()))
        self.damage_quantity.setText(str(self.damage_model.index(row, 3).data()))

    def add_damage(self):
        date, product, qty = self.damage_date.text(), self.damage_product.text(), self.damage_quantity.text()
        if not all([date, product, qty]):
            self.create_message_box("Error", "All fields required!", QMessageBox.Warning).exec()
            return
        try:
            datetime.strptime(date, "%Y-%m-%d")
            qty = int(qty)
            if qty <= 0:
                raise ValueError("Quantity must be positive!")
            self.cursor.execute("SELECT id, stock FROM products WHERE name = ?", (product,))
            result = self.cursor.fetchone()
            if not result:
                raise ValueError(f"Product '{product}' not found!")
            prod_id, stock = result
            if stock < qty:
                raise ValueError(f"Insufficient stock: {stock} available!")
            
            new_stock = self.update_stock(prod_id, -qty, f"Damaged {qty} units")
            if new_stock is None:
                return
            
            self.cursor.execute("INSERT INTO damaged_products (date, product_name, quantity, product_id, replaced) VALUES (?, ?, ?, ?, 0)",
                               (date, product, qty, prod_id))
            self.conn.commit()
            self.load_data()
            self.clear_log_fields('damage')
            self.statusBar.showMessage(f"Damage of {qty} '{product}' added", 5000)
            logging.info(f"Damage of {qty} '{product}' added")
        except ValueError as e:
            self.create_message_box("Error", str(e), QMessageBox.Warning).exec()

    def replace_damage(self):
        if not self.damage_table.currentIndex().isValid():
            self.create_message_box("Error", "Select a damage entry!", QMessageBox.Warning).exec()
            return
        row = self.damage_table.currentIndex().row()
        damage_id = self.damage_model.index(row, 0).data()
        product = self.damage_model.index(row, 2).data()
        qty = self.damage_model.index(row, 3).data()
        prod_id = self.damage_model.index(row, 4).data()
        replaced = self.damage_model.index(row, 5).data()
        if replaced == 1:
            self.create_message_box("Error", "Already replaced!", QMessageBox.Warning).exec()
            return
        reply = self.create_message_box("Confirm", f"Replace {qty} damaged '{product}'?", QMessageBox.Question, QMessageBox.Yes | QMessageBox.No)
        if reply.exec() == QMessageBox.Yes:
            try:
                self.update_stock(prod_id, qty, f"Replaced {qty} damaged units")
                self.cursor.execute("UPDATE damaged_products SET replaced=1 WHERE id=?", (damage_id,))
                self.conn.commit()
                self.load_data()
                self.clear_log_fields('damage')
                logging.info(f"Replaced {qty} damaged '{product}'")
            except sqlite3.Error as e:
                logging.error(f"Failed to replace damage: {e}")
                self.create_message_box("Error", f"Failed to replace damage: {e}", QMessageBox.Critical).exec()

    def delete_damage(self):
        if not self.damage_table.currentIndex().isValid():
            self.create_message_box("Error", "Select a damage entry!", QMessageBox.Warning).exec()
            return
        row = self.damage_table.currentIndex().row()
        damage_id = self.damage_model.index(row, 0).data()
        product = self.damage_model.index(row, 2).data()
        qty = self.damage_model.index(row, 3).data()
        prod_id = self.damage_model.index(row, 4).data()
        replaced = self.damage_model.index(row, 5).data()
        reply = self.create_message_box("Confirm", f"Delete damage of {qty} '{product}'?", QMessageBox.Question, QMessageBox.Yes | QMessageBox.No)
        if reply.exec() == QMessageBox.Yes:
            try:
                if replaced == 0:
                    self.update_stock(prod_id, qty, f"Deleted damage entry ({qty} units)")
                self.cursor.execute("DELETE FROM damaged_products WHERE id=?", (damage_id,))
                self.conn.commit()
                self.load_data()
                self.clear_log_fields('damage')
                self.statusBar.showMessage(f"Damage entry for '{product}' deleted", 5000)
                logging.info(f"Damage entry for '{product}' deleted")
            except sqlite3.Error as e:
                logging.error(f"Failed to delete damage: {e}")
                self.create_message_box("Error", f"Failed to delete damage: {e}", QMessageBox.Critical).exec()

    def toggle_sale_selector(self, index):
        is_from_sale = self.invoice_source.currentText() == "From Sale"
        self.sale_selector.setEnabled(is_from_sale)
        self.product_selector.setEnabled(not is_from_sale)
        self.invoice_quantity.setEnabled(not is_from_sale)
        self.invoice_discount.setEnabled(not is_from_sale)
        if not is_from_sale:
            self.sale_selector.setCurrentIndex(0)
            self.product_selector.setCurrentIndex(0)
            self.invoice_quantity.clear()
            self.invoice_discount.clear()

    def on_sale_select(self, index):
        sale_id = self.sale_selector.itemData(index)
        if sale_id:
            self.cursor.execute("SELECT item, quantity, discount FROM daily_accessories_sales WHERE id = ?", (sale_id,))
            result = self.cursor.fetchone()
            if result:
                item, qty, discount = result
                self.product_selector.setCurrentText(item)
                self.invoice_quantity.setText(str(qty))
                self.invoice_discount.setText(str(discount))
            else:
                logging.warning(f"No data found for sale ID: {sale_id}")
                self.create_message_box("Error", f"Sale ID {sale_id} not found!", QMessageBox.Warning).exec()

    def refresh_sale_selector(self):
        self.sale_selector.clear()
        self.sale_selector.addItem("Select a Sale", None)
        self.cursor.execute("SELECT id, item, quantity FROM daily_accessories_sales ORDER BY id DESC")
        for sale_id, item, qty in self.cursor.fetchall():
            self.sale_selector.addItem(f"Sale #{sale_id}: {item} ({qty})", sale_id)

    def add_invoice(self):
        date = self.invoice_date.text()
        customer_name = self.customer_name.text()
        source = self.invoice_source.currentText()
        sale_id = self.sale_selector.currentData() if source == "From Sale" else None
        
        if source == "From Stock":
            product_name = self.product_selector.currentText()
            qty = self.invoice_quantity.text()
            discount = self.invoice_discount.text() or "0"
            required_fields = [date, customer_name, product_name, qty]
        else:
            if not sale_id:
                self.create_message_box("Error", "Please select a sale!", QMessageBox.Warning).exec()
                return
            self.cursor.execute("SELECT item, quantity, discount FROM daily_accessories_sales WHERE id = ?", (sale_id,))
            result = self.cursor.fetchone()
            if not result:
                self.create_message_box("Error", f"Sale ID {sale_id} not found!", QMessageBox.Critical).exec()
                return
            product_name, qty, discount = result
            required_fields = [date, customer_name]

        if not all(required_fields):
            self.create_message_box("Error", "All required fields must be filled!", QMessageBox.Warning).exec()
            return

        try:
            datetime.strptime(date, "%Y-%m-%d")
            qty = int(qty)
            discount = float(discount)
            if qty <= 0:
                raise ValueError("Quantity must be positive!")
            if discount < 0 or discount > 100:
                raise ValueError("Discount must be between 0 and 100%!")
            
            self.cursor.execute("SELECT id, sell_price, stock FROM products WHERE name = ?", (product_name,))
            result = self.cursor.fetchone()
            if not result:
                raise ValueError(f"Product '{product_name}' not found!")
            prod_id, unit_price, stock = result

            if source == "From Sale" and sale_id:
                self.cursor.execute("SELECT quantity, product_id, discount FROM daily_accessories_sales WHERE id = ?", (sale_id,))
                sale_data = self.cursor.fetchone()
                if not sale_data or sale_data[1] != prod_id or sale_data[0] != qty or sale_data[2] != discount:
                    raise ValueError("Selected sale does not match product, quantity, or discount!")
            elif source == "From Stock":
                if stock < qty:
                    raise ValueError(f"Insufficient stock: {stock} available!")

            subtotal = qty * unit_price
            discount_amount = subtotal * (discount / 100)
            total = subtotal - discount_amount
            vat_rate = 0.13
            vat = total * vat_rate
            grand_total = total + vat
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            invoice_number = f"INV-{timestamp.replace(' ', '-').replace(':', '')}"

            self.cursor.execute("SELECT COUNT(*) FROM invoices WHERE invoice_number = ?", (invoice_number,))
            if self.cursor.fetchone()[0] > 0:
                raise ValueError(f"Invoice number '{invoice_number}' already exists!")

            self.cursor.execute("INSERT INTO invoices (invoice_number, date, customer_name, total, vat, grand_total, timestamp, sale_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                               (invoice_number, date, customer_name, total, vat, grand_total, timestamp, sale_id))
            invoice_id = self.cursor.lastrowid
            self.cursor.execute("INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price, discount, total) VALUES (?, ?, ?, ?, ?, ?)",
                               (invoice_id, prod_id, qty, unit_price, discount, total))
            
            if source == "From Stock":
                self.update_stock(prod_id, -qty, f"Invoice {invoice_number}")
            
            self.conn.commit()
            self.load_data()
            self.clear_invoice_fields()
            self.statusBar.showMessage(f"Invoice '{invoice_number}' added", 5000)
            logging.info(f"Invoice '{invoice_number}' added {'from sale' if sale_id else 'from stock'} with {discount}% discount")

            items = [(product_name, qty, unit_price, discount, total)]
            reply = self.create_message_box("Invoice Created", f"Invoice '{invoice_number}' created successfully.\nWould you like to download or print it?",
                                           QMessageBox.Information, QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            reply_val = reply.exec()
            if reply_val == QMessageBox.Yes:
                self.save_invoice_to_pdf(invoice_number, date, customer_name, total, vat, grand_total, items)
            elif reply_val == QMessageBox.No:
                self.print_invoice(invoice_number, date, customer_name, total, vat, grand_total, items)

        except ValueError as e:
            self.create_message_box("Error", str(e), QMessageBox.Warning).exec()
        except sqlite3.Error as e:
            logging.error(f"Database error in add_invoice: {e}")
            self.create_message_box("Error", f"Database error: {e}", QMessageBox.Critical).exec()

    def generate_invoice_html(self, invoice_number, date, customer_name, total, vat, grand_total, items):
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; color: {TEXT_COLOR}; margin: 20px; }}
                .header {{ text-align: center; background-color: {HEADER_BG}; color: white; padding: 10px; border-radius: 8px; }}
                .details {{ margin: 20px 0; }}
                .details-table {{ width: 100%; border-collapse: collapse; }}
                .details-table td {{ padding: 5px; }}
                .items-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                .items-table th, .items-table td {{ border: 1px solid {BORDER_COLOR}; padding: 8px; text-align: left; }}
                .items-table th {{ background-color: {ACCENT_COLOR}; color: white; font-weight: bold; }}
                .totals {{ margin-top: 20px; text-align: right; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>Invoice #{invoice_number}</h2>
            </div>
            <table class="details-table">
                <tr><td><strong>Date:</strong></td><td>{date}</td></tr>
                <tr><td><strong>Company:</strong></td><td>{self.company_name} (PAN: {self.pan_number})</td></tr>
                <tr><td><strong>Customer:</strong></td><td>{customer_name}</td></tr>
            </table>
            <table class="items-table">
                <tr><th>Description</th><th>Quantity</th><th>Unit Price (NPR)</th><th>Discount (%)</th><th>Total (NPR)</th></tr>
        """
        for item in items:
            html += f"<tr><td>{item[0]}</td><td>{item[1]}</td><td>{item[2]:.2f}</td><td>{item[3]:.2f}</td><td>{item[4]:.2f}</td></tr>"
        html += f"""
            </table>
            <div class="totals">
                <p><strong>Subtotal:</strong> NPR {total:.2f}</p>
                <p><strong>VAT (13%):</strong> NPR {vat:.2f}</p>
                <p><strong>Grand Total:</strong> NPR {grand_total:.2f}</p>
            </div>
            <div class="footer">
                Generated by IRD-Compliant PMS Software
            </div>
        </body>
        </html>
        """
        return html

    def save_invoice_to_pdf(self, invoice_number, date, customer_name, total, vat, grand_total, items):
        path, _ = QFileDialog.getSaveFileName(self, "Save Invoice as PDF", f"invoice_{invoice_number}.pdf", "PDF Files (*.pdf)")
        if path:
            try:
                pdf = QPdfWriter(path)
                pdf.setPageSize(QPageSize(QPageSize.A4))
                pdf.setResolution(100)
                document = QTextDocument()
                document.setHtml(self.generate_invoice_html(invoice_number, date, customer_name, total, vat, grand_total, items))
                document.print_(pdf)
                self.statusBar.showMessage(f"Invoice saved to {path}", 5000)
                logging.info(f"Invoice '{invoice_number}' saved to {path}")
            except Exception as e:
                logging.error(f"Failed to save invoice as PDF: {e}")
                self.create_message_box("Error", f"Failed to save invoice: {e}", QMessageBox.Critical).exec()

    def print_invoice(self, invoice_number, date, customer_name, total, vat, grand_total, items):
        try:
            printer = QPrinter(QPrinter.HighResolution)
            dialog = QPrintDialog(printer, self)
            if dialog.exec() == QPrintDialog.Accepted:
                document = QTextDocument()
                document.setHtml(self.generate_invoice_html(invoice_number, date, customer_name, total, vat, grand_total, items))
                document.print_(printer)
                self.statusBar.showMessage(f"Invoice '{invoice_number}' printed", 5000)
                logging.info(f"Invoice '{invoice_number}' printed")
        except Exception as e:
            logging.error(f"Failed to print invoice: {e}")
            self.create_message_box("Error", f"Failed to print invoice: {e}", QMessageBox.Critical).exec()

    def on_invoice_select(self, index):
        row = index.row()
        self.invoice_date.setText(str(self.invoice_model.index(row, 2).data()))
        self.customer_name.setText(str(self.invoice_model.index(row, 3).data()))
        sale_id = self.invoice_model.index(row, 7).data()
        if sale_id:
            self.invoice_source.setCurrentText("From Sale")
            self.sale_selector.setCurrentIndex(self.sale_selector.findData(sale_id))
        else:
            self.invoice_source.setCurrentText("From Stock")
            self.cursor.execute("SELECT p.name, ii.quantity, ii.discount FROM invoice_items ii JOIN products p ON ii.product_id = p.id WHERE ii.invoice_id = ?",
                               (self.invoice_model.index(row, 0).data(),))
            result = self.cursor.fetchone()
            if result:
                product_name, qty, discount = result
                self.product_selector.setCurrentText(product_name)
                self.invoice_quantity.setText(str(qty))
                self.invoice_discount.setText(str(discount))

    def view_invoice(self):
        if not self.invoice_table.currentIndex().isValid():
            self.create_message_box("Error", "Select an invoice to view!", QMessageBox.Warning).exec()
            return
        
        row = self.invoice_table.currentIndex().row()
        invoice_id = self.invoice_model.index(row, 0).data()
        invoice_number = self.invoice_model.index(row, 1).data()
        date = self.invoice_model.index(row, 2).data()
        customer_name = self.invoice_model.index(row, 3).data()
        total = float(self.invoice_model.index(row, 4).data())
        vat = float(self.invoice_model.index(row, 5).data())
        grand_total = float(self.invoice_model.index(row, 6).data())

        self.cursor.execute("SELECT p.name, ii.quantity, ii.unit_price, ii.discount, ii.total FROM invoice_items ii JOIN products p ON ii.product_id = p.id WHERE ii.invoice_id = ?", (invoice_id,))
        items = self.cursor.fetchall()

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Invoice #{invoice_number}")
        dialog.setFixedSize(600, 700)
        dialog.setStyleSheet(f"background-color: {PRIMARY_BG};")
        layout = QVBoxLayout(dialog)

        header = QLabel(f"Invoice #{invoice_number}")
        header.setStyleSheet(f"background-color: {HEADER_BG}; color: white; padding: 10px; font-size: 18px; font-weight: bold; text-align: center; border-radius: 8px;")
        layout.addWidget(header)

        details_widget = QWidget()
        details_layout = QGridLayout(details_widget)
        details_widget.setStyleSheet(f"background-color: {SECONDARY_BG}; padding: 10px; border-radius: 8px; margin: 10px 0;")
        details = [
            ("Date:", date),
            ("Company:", f"{self.company_name} (PAN: {self.pan_number})"),
            ("Customer:", customer_name)
        ]
        for i, (label, value) in enumerate(details):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 14px; font-weight: bold;")
            val = QLabel(value)
            val.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 14px;")
            details_layout.addWidget(lbl, i, 0)
            details_layout.addWidget(val, i, 1)
        layout.addWidget(details_widget)

        items_table = QTableWidget()
        items_table.setRowCount(len(items))
        items_table.setColumnCount(5)
        items_table.setHorizontalHeaderLabels(["Description", "Quantity", "Unit Price (NPR)", "Discount (%)", "Total (NPR)"])
        items_table.horizontalHeader().setStyleSheet(f"background-color: {ACCENT_COLOR}; color: white; font-weight: bold;")
        items_table.setStyleSheet(f"QTableWidget {{ background-color: {SECONDARY_BG}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 13px; font-weight: bold; }} QTableWidget::item:selected {{ background-color: {HOVER_COLOR}; color: white; }}")
        items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for row_idx, item in enumerate(items):
            items_table.setItem(row_idx, 0, QTableWidgetItem(item[0]))
            items_table.setItem(row_idx, 1, QTableWidgetItem(str(item[1])))
            items_table.setItem(row_idx, 2, QTableWidgetItem(f"{item[2]:.2f}"))
            items_table.setItem(row_idx, 3, QTableWidgetItem(f"{item[3]:.2f}"))
            items_table.setItem(row_idx, 4, QTableWidgetItem(f"{item[4]:.2f}"))
        layout.addWidget(items_table)

        totals_widget = QWidget()
        totals_layout = QVBoxLayout(totals_widget)
        totals_widget.setStyleSheet(f"background-color: {SECONDARY_BG}; padding: 10px; border-radius: 8px; margin: 10px 0;")
        totals = [
            (f"Subtotal: NPR {total:.2f}", TOTAL_COLOR),
            (f"VAT (13%): NPR {vat:.2f}", TEXT_COLOR),
            (f"Grand Total: NPR {grand_total:.2f}", PROFIT_COLOR)
        ]
        for text, color in totals:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold; text-align: right;")
            totals_layout.addWidget(lbl)
        layout.addWidget(totals_widget)

        buttons_layout = QHBoxLayout()
        download_btn = QPushButton("Download PDF")
        download_btn.clicked.connect(lambda: self.save_invoice_to_pdf(invoice_number, date, customer_name, total, vat, grand_total, items))
        print_btn = QPushButton("Print")
        print_btn.clicked.connect(lambda: self.print_invoice(invoice_number, date, customer_name, total, vat, grand_total, items))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        for btn, color in [(download_btn, ACCENT_COLOR), (print_btn, PROFIT_COLOR), (close_btn, DELETE_COLOR)]:
            btn.setStyleSheet(f"background-color: {color}; color: white; padding: 10px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none;")
            buttons_layout.addWidget(btn)
        layout.addLayout(buttons_layout)

        footer = QLabel("Generated by IRD-Compliant PMS Software")
        footer.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 12px; text-align: center;")
        layout.addWidget(footer)

        dialog.exec()

    def delete_invoice(self):
        if not self.invoice_table.currentIndex().isValid():
            self.create_message_box("Error", "Select an invoice to delete!", QMessageBox.Warning).exec()
            return
        
        row = self.invoice_table.currentIndex().row()
        invoice_id = self.invoice_model.index(row, 0).data()
        invoice_number = self.invoice_model.index(row, 1).data()
        sale_id = self.invoice_model.index(row, 7).data()
        
        reply = self.create_message_box("Confirm", f"Delete invoice '{invoice_number}'?", QMessageBox.Question, QMessageBox.Yes | QMessageBox.No)
        if reply.exec() == QMessageBox.Yes:
            self.cursor.execute("SELECT product_id, quantity FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
            items = self.cursor.fetchall()
            if not sale_id:
                for prod_id, qty in items:
                    self.update_stock(prod_id, qty, f"Invoice {invoice_number} deletion")
            self.cursor.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
            self.cursor.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
            self.conn.commit()
            self.load_data()
            self.clear_invoice_fields()
            self.statusBar.showMessage(f"Invoice '{invoice_number}' deleted", 5000)
            logging.info(f"Invoice '{invoice_number}' deleted")

    def clear_invoice_fields(self):
        self.invoice_date.setText(self.current_date)
        self.customer_name.clear()
        self.product_selector.setCurrentIndex(0)
        self.invoice_quantity.clear()
        self.invoice_discount.clear()
        self.invoice_source.setCurrentIndex(0)
        self.sale_selector.setCurrentIndex(0)

    def browse_qr(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select QR Code Image", "", "Image Files (*.png *.jpg *.jpeg)")
        if path:
            self.qr_path.setText(path)

    def add_qr_payment(self):
        name = self.qr_name.text()
        path = self.qr_path.text()
        if not all([name, path]):
            self.create_message_box("Error", "Name and QR image required!", QMessageBox.Warning).exec()
            return
        
        dest_path = os.path.join(QR_STORAGE_DIR, f"{name}_{os.path.basename(path)}")
        try:
            shutil.copy(path, dest_path)
            self.cursor.execute("INSERT INTO qr_payments (name, image_path) VALUES (?, ?)", (name, dest_path))
            self.conn.commit()
            self.load_data()
            self.qr_name.clear()
            self.qr_path.clear()
            self.statusBar.showMessage(f"QR Payment '{name}' added", 5000)
            logging.info(f"QR Payment '{name}' added")
        except Exception as e:
            logging.error(f"Failed to add QR payment: {e}")
            self.create_message_box("Error", f"Failed to add QR payment: {e}", QMessageBox.Critical).exec()

    def on_qr_select(self, index):
        row = index.row()
        self.qr_name.setText(str(self.qr_model.index(row, 1).data()))
        self.qr_path.setText(str(self.qr_model.index(row, 2).data()))

    def view_qr(self):
        if not self.qr_table.currentIndex().isValid():
            self.create_message_box("Error", "Select a QR to view!", QMessageBox.Warning).exec()
            return
        
        row = self.qr_table.currentIndex().row()
        name = self.qr_model.index(row, 1).data()
        path = self.qr_model.index(row, 2).data()
        
        if os.path.exists(path):
            dialog = QDialog(self)
            dialog.setWindowTitle(f"QR Code: {name}")
            dialog.setFixedSize(500, 600)
            dialog.setStyleSheet(f"background-color: {PRIMARY_BG};")
            layout = QVBoxLayout(dialog)

            header = QLabel(f"QR Code: {name}")
            header.setStyleSheet(f"background-color: {HEADER_BG}; color: white; padding: 10px; font-size: 18px; font-weight: bold; text-align: center; border-radius: 8px;")
            layout.addWidget(header)

            scene = QGraphicsScene()
            view = QGraphicsView(scene)
            view.setStyleSheet(f"background-color: {SECONDARY_BG}; border: 1px solid {BORDER_COLOR}; border-radius: 8px;")
            pixmap = QPixmap(path)
            scene.addPixmap(pixmap.scaled(450, 450, Qt.KeepAspectRatio))
            layout.addWidget(view)

            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            close_btn.setStyleSheet(f"background-color: {DELETE_COLOR}; color: white; padding: 10px; border-radius: 6px; font-family: Segoe UI; font-size: 14px; font-weight: bold; border: none;")
            layout.addWidget(close_btn, alignment=Qt.AlignCenter)

            dialog.exec()
        else:
            self.create_message_box("Error", "QR image not found!", QMessageBox.Warning).exec()

    def delete_qr(self):
        if not self.qr_table.currentIndex().isValid():
            self.create_message_box("Error", "Select a QR to delete!", QMessageBox.Warning).exec()
            return
        
        row = self.qr_table.currentIndex().row()
        qr_id = self.qr_model.index(row, 0).data()
        name = self.qr_model.index(row, 1).data()
        path = self.qr_model.index(row, 2).data()
        
        reply = self.create_message_box("Confirm", f"Delete QR '{name}'?", QMessageBox.Question, QMessageBox.Yes | QMessageBox.No)
        if reply.exec() == QMessageBox.Yes:
            try:
                if os.path.exists(path):
                    os.remove(path)
                self.cursor.execute("DELETE FROM qr_payments WHERE id = ?", (qr_id,))
                self.conn.commit()
                self.load_data()
                self.qr_name.clear()
                self.qr_path.clear()
                self.statusBar.showMessage(f"QR '{name}' deleted", 5000)
                logging.info(f"QR '{name}' deleted")
            except Exception as e:
                logging.error(f"Failed to delete QR: {e}")
                self.create_message_box("Error", f"Failed to delete QR: {e}", QMessageBox.Critical).exec()

    def backup_data(self):
        backup_dir = self.config.get('Settings', 'backup_dir', fallback=BACKUP_DIR)
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"backup_{timestamp}.db")
        try:
            shutil.copy2(DB_PATH, backup_path)
            self.statusBar.showMessage(f"Backup created at {backup_path}", 5000)
            logging.info(f"Backup created at {backup_path}")
        except Exception as e:
            logging.error(f"Backup failed: {e}")
            self.create_message_box("Error", f"Backup failed: {e}", QMessageBox.Critical).exec()

    def automatic_backup(self):
        current_date = datetime.now().strftime("%Y-%m-%d")
        if current_date != self.last_backup_date:
            self.backup_data()
            self.last_backup_date = current_date
            logging.info(f"Automatic daily backup performed for {current_date}")

    def restore_data(self):
        backup_dir = self.config.get('Settings', 'backup_dir', fallback=BACKUP_DIR)
        path, _ = QFileDialog.getOpenFileName(self, "Select Backup", backup_dir, "SQLite Database (*.db)")
        if path:
            try:
                self.db.close()
                self.conn.close()
                shutil.copy2(path, DB_PATH)
                self.setup_databases()
                self.product_names = self.get_product_names()
                self.load_data()
                self.statusBar.showMessage(f"Data restored from {path}", 5000)
                logging.info(f"Data restored from {path}")
            except Exception as e:
                logging.error(f"Restore failed: {e}")
                self.create_message_box("Error", f"Restore failed: {e}", QMessageBox.Critical).exec()

    def show_stock_history(self):
        if not self.table.currentIndex().isValid():
            self.create_message_box("Error", "Select a product to view stock history!", QMessageBox.Warning).exec()
            return
        
        row = self.filter_model.mapToSource(self.table.currentIndex()).row()
        prod_id = self.table_model.index(row, 0).data()
        prod_name = self.table_model.index(row, 1).data()
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Stock History: {prod_name}")
        dialog.setFixedSize(600, 400)
        layout = QVBoxLayout(dialog)
        
        history_table = QTableWidget()
        self.cursor.execute("SELECT date, quantity_change, reason FROM stock_history WHERE product_id = ? ORDER BY date DESC", (prod_id,))
        history = self.cursor.fetchall()
        
        history_table.setRowCount(len(history))
        history_table.setColumnCount(3)
        history_table.setHorizontalHeaderLabels(["Date", "Quantity Change", "Reason"])
        history_table.horizontalHeader().setStyleSheet(f"background-color: {ACCENT_COLOR}; color: white; font-weight: bold;")
        history_table.setStyleSheet(f"QTableWidget {{ background-color: {SECONDARY_BG}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; color: {TEXT_COLOR}; font-family: Segoe UI; font-size: 13px; font-weight: bold; }}")
        history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        for row_idx, (date, qty, reason) in enumerate(history):
            history_table.setItem(row_idx, 0, QTableWidgetItem(date))
            history_table.setItem(row_idx, 1, QTableWidgetItem(str(qty)))
            history_table.setItem(row_idx, 2, QTableWidgetItem(reason))
        
        layout.addWidget(history_table)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        close_btn.setStyleSheet(f"background-color: {DELETE_COLOR}; color: white; padding: 10px; border-radius: 6px;")
        layout.addWidget(close_btn)
        
        dialog.exec()

    def show_about(self):
        self.create_message_box("About", f"PMS v{VERSION}\nDeveloped by Karan Jung Budhathoki\n© 2025\nEmail: underside001@gmail.com").exec()

    def load_data(self):
        self.table_model.select()
        self.sales_model.select()
        self.bank_model.select()
        self.expenses_model.select()
        self.damage_model.select()
        self.invoice_model.select()
        self.qr_model.select()
        self.refresh_sale_selector()
        self.update_totals()
        if hasattr(self, 'dashboard_tab'):
            self.dashboard_tab.refresh()

    def clear_fields(self):
        self.id_input.clear()
        self.name_input.clear()
        self.type_selector.setCurrentText("")
        self.buy_price_input.clear()
        self.sell_price_input.clear()
        self.stock_input.clear()
        self.search_name_input.clear()
        self.search_type_combo.setCurrentIndex(0)
        self.min_buy_input.clear()
        self.max_buy_input.clear()
        self.min_sell_input.clear()
        self.max_sell_input.clear()
        self.updated_after_input.clear()
        self.stock_min_input.clear()
        self.stock_max_input.clear()
        self.filter_model.resetFilters()
        self.table_model.select()

    def export_to_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if path:
            try:
                self.cursor.execute("SELECT * FROM products")
                with open(path, 'w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(["ID", "Name", "Type", "Buy Price", "Sell Price", "Last Updated", "Stock"])
                    writer.writerows(self.cursor.fetchall())
                self.statusBar.showMessage(f"Data exported to {path}", 5000)
                self.create_message_box("Success", "Data exported successfully!").exec()
                logging.info(f"Data exported to {path}")
            except Exception as e:
                logging.error(f"Export failed: {e}")
                self.create_message_box("Error", f"Export failed: {e}", QMessageBox.Critical).exec()

    def import_from_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if path:
            try:
                with open(path, 'r') as file:
                    reader = csv.reader(file)
                    header = next(reader)
                    self.conn.execute("BEGIN TRANSACTION")
                    for row in reader:
                        if len(row) >= 6:
                            id_, name, type_, buy_price, sell_price, last_updated, stock = row[:7]
                            self.cursor.execute("INSERT OR REPLACE INTO products (name, type, buy_price, sell_price, last_updated, stock) VALUES (?, ?, ?, ?, ?, ?)",
                                               (name, type_, float(buy_price), float(sell_price), last_updated, int(stock or 0)))
                            product_id = self.cursor.lastrowid
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            self.cursor.execute("INSERT INTO stock_history (product_id, date, quantity_change, reason) VALUES (?, ?, ?, ?)",
                                               (product_id, timestamp, int(stock or 0), "Imported stock"))
                    self.conn.commit()
                self.product_names = self.get_product_names()
                self.sales_completer.setModel(QStringListModel(self.product_names))
                self.damage_completer.setModel(QStringListModel(self.product_names))
                self.product_selector.clear()
                self.product_selector.addItems(self.product_names)
                self.load_data()
                self.statusBar.showMessage(f"Data imported from {path}", 5000)
                self.create_message_box("Success", "Data imported successfully!").exec()
                logging.info(f"Data imported from {path}")
            except Exception as e:
                self.conn.rollback()
                logging.error(f"Import failed: {e}")
                self.create_message_box("Error", f"Import failed: {e}", QMessageBox.Critical).exec()

    def get_input_data(self):
        name = self.name_input.text().strip()
        type_ = self.type_selector.currentText()
        buy_price = self.buy_price_input.text().strip()
        sell_price = self.sell_price_input.text().strip()
        stock = self.stock_input.text().strip() or "0"
        
        if not all([name, type_, buy_price, sell_price]):
            return None
        
        try:
            buy_price = float(buy_price)
            sell_price = float(sell_price)
            stock = int(stock)
            if buy_price < 0 or sell_price < 0 or stock < 0:
                raise ValueError("Negative values not allowed")
            return (name, type_, buy_price, sell_price, stock)
        except ValueError as e:
            self.create_message_box("Error", str(e) if str(e) != "Negative values not allowed" else "Numeric fields must be valid non-negative!", QMessageBox.Warning).exec()
            return None

    def debounce_search(self):
        QTimer.singleShot(300, self.apply_filters)

    def apply_filters(self):
        kwargs = {
            'name': self.search_name_input.text().strip(),
            'type': self.search_type_combo.currentText(),
            'min_buy': self.safe_float(self.min_buy_input.text()),
            'max_buy': self.safe_float(self.max_buy_input.text()),
            'min_sell': self.safe_float(self.min_sell_input.text()),
            'max_sell': self.safe_float(self.max_sell_input.text()),
            'updated_after': self.safe_date(self.updated_after_input.text()),
            'stock_min': self.safe_int(self.stock_min_input.text()),
            'stock_max': self.safe_int(self.stock_max_input.text())
        }
        self.filter_model.setFilterCriteria(**kwargs)

    def safe_float(self, text):
        try:
            return float(text.strip()) if text.strip() else None
        except ValueError:
            return None

    def safe_int(self, text):
        try:
            return int(text.strip()) if text.strip() else None
        except ValueError:
            return None

    def safe_date(self, text):
        try:
            return datetime.strptime(text.strip(), "%Y-%m-%d").strftime("%Y-%m-%d %H:%M:%S") if text.strip() else None
        except ValueError:
            return None

    def toggle_advanced_search(self, state):
        self.advanced_search_widget.setVisible(state == Qt.Checked)
        self.apply_filters()

    def update_totals(self):
        try:
            self.cursor.execute("SELECT SUM(total) FROM daily_accessories_sales")
            sales_total = self.cursor.fetchone()[0] or 0
            self.sales_total.setText(f"Total Sales: NPR {sales_total:.2f}")
            
            self.cursor.execute("SELECT SUM(quantity) FROM damaged_products WHERE replaced = 0")
            damage_total = self.cursor.fetchone()[0] or 0
            self.damage_total.setText(f"Total Damaged: {damage_total}")
            
            self.cursor.execute("SELECT SUM(amount) FROM bank_transactions WHERE type='profit'")
            profit_total = self.cursor.fetchone()[0] or 0
            self.cursor.execute("SELECT SUM(amount) FROM bank_transactions WHERE type='expense'")
            expense_total = abs(self.cursor.fetchone()[0] or 0)
            bank_total = profit_total - expense_total
            self.bank_total.setText(f"Total Bank: NPR {bank_total:.2f}")
            
            self.cursor.execute("SELECT SUM(amount) FROM expenses")
            expenses_total = self.cursor.fetchone()[0] or 0
            self.expenses_total.setText(f"Total Expenses: NPR {expenses_total:.2f}")
        except sqlite3.Error as e:
            logging.error(f"Failed to update totals: {e}")
            self.sales_total.setText("Total Sales: Error")
            self.damage_total.setText("Total Damaged: Error")
            self.bank_total.setText("Total Bank: Error")
            self.expenses_total.setText("Total Expenses: Error")

    def clear_log_fields(self, section):
        today = self.current_date
        fields = {
            'sales': [self.sales_item, self.sales_quantity, self.sales_price, self.sales_discount],
            'bank': [self.bank_amount, self.bank_desc],
            'expenses': [self.expenses_desc, self.expenses_amount],
            'damage': [self.damage_product, self.damage_quantity]
        }
        date_fields = {
            'sales': self.sales_date,
            'bank': self.bank_date,
            'expenses': self.expenses_date,
            'damage': self.damage_date
        }
        for widget in fields.get(section, []):
            widget.clear()
        if section in date_fields:
            date_fields[section].setText(today)

    def closeEvent(self, event):
        self.conn.close()
        self.db.close()
        self.backup_timer.stop()
        logging.info("Application closed")
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(PRIMARY_BG))
    palette.setColor(QPalette.Button, QColor(ACCENT_COLOR))
    palette.setColor(QPalette.Text, QColor(TEXT_COLOR))
    palette.setColor(QPalette.ButtonText, QColor("white"))
    palette.setColor(QPalette.Highlight, QColor(HOVER_COLOR))
    palette.setColor(QPalette.Base, QColor(SECONDARY_BG))
    app.setPalette(palette)
    window = ProductManagementApp()
    window.show()
    sys.exit(app.exec())