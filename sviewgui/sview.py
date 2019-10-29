import sys
from PyQt5 import QtCore as Qc, QtGui as Qg, QtWidgets as Qw   
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import matplotlib
matplotlib.use("Qt5Agg")
import os
import re
import glob
import numpy as np
import pandas as pd
import random
from . import sgui as gui

import matplotlib.cm
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap

from pathlib import Path
from PyQt5.Qt import PYQT_VERSION_STR
from datetime import datetime

import scipy.stats as st

import cmocean
import cmocean.cm
import seaborn as sns

import pygments

#==================
# Display pandas dataframe at QTableWidget
#==================
class PandasModel(Qc.QAbstractTableModel): 
    def __init__(self, df = pd.DataFrame(), parent=None): 
        Qc.QAbstractTableModel.__init__(self, parent=parent)
        self._df = df

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return Qc.QVariant()

        if orientation == Qt.Horizontal:
            try:
                return self._df.columns.tolist()[section]
            except (IndexError, ):
                return Qc.QVariant()
        elif orientation == Qt.Vertical:
            try:
                return self._df.index.tolist()[section]
            except (IndexError, ):
                return Qc.QVariant()

    def data(self, index, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return Qc.QVariant()

        if not index.isValid():
            return Qc.QVariant()

        return Qc.QVariant(str(self._df.iloc[index.row(), index.column()])) 

    def setData(self, index, value, role):
        row = self._df.index[index.row()]
        col = self._df.columns[index.column()]
        if hasattr(value, 'toPyObject'):
            # PyQt4 gets a QVariant
            value = value.toPyObject()
        else:
            # PySide gets an unicode
            dtype = self._df[col].dtype
            if dtype != object:
                value = None if value == '' else dtype.type(value)
        self._df.set_value(row, col, value)
        return True

    def rowCount(self, parent=Qc.QModelIndex()): 
        return len(self._df.index)

    def columnCount(self, parent=Qc.QModelIndex()): 
        return len(self._df.columns)

    def sort(self, column, order):
        colname = self._df.columns.tolist()[column]
        self.layoutAboutToBeChanged.emit()
        self._df.sort_values(colname, ascending= order == Qt.AscendingOrder, inplace=True)
        self._df.reset_index(inplace=True, drop=True)
        self.layoutChanged.emit()


#==================
## Main Window #####
#==================
class Csviwer(Qw.QMainWindow):
    SCATTER = 0; DENSITY = 1; HISTGRAM = 2; LINE = 3; BOXPLOT = 4
    STYLE = "monokai"              
    def __init__(self, parent=None, data=None):        
        super().__init__(parent)
        self.initUI(data)
    
    def initUI(self,data):
        self.ui = gui.Ui_MainWindow()  
        self.ui.setupUi(self)               
        self.ui.logbox.setStyleSheet("background-color: rgb(39, 40, 34);")
        self.ui.logbox.document().setDefaultStyleSheet(pygments.formatters.HtmlFormatter(style=Csviwer.STYLE).get_style_defs('.highlight'))
        initial_str = "#Graph drawer"+"\n"+"#Just for plotting by matplotlib."+"\n"+"#========================"+"\n"+"# package ----"+"\n"+"import numpy as np"+"\n"+"import pandas as pd"+"\n"+"import matplotlib.pyplot as plt"+"\n"+"import seaborn as sns"+"\n"+"import cmocean"+"\n"+"# -------------"
        lexer = pygments.lexers.get_lexer_by_name('python3')
        formatter = pygments.formatters.get_formatter_by_name('html')
        html = pygments.highlight(initial_str,lexer,formatter)
        self.ui.logbox.append(html)
        self.ui.logbox.moveCursor(Qg.QTextCursor.End)
        self.CSV_PATH = "" # Path of csv
        self.HEADER_LIST = [] # List of header name of CSV file
        self.NUMERIC_HEADER_LIST = [] # List of header name of CSV file (only numeric data)
        self.SAVE_DIR = "" # Folda path where the graph will be exported
        self.SAVE_FILE_NAME = "" # Name of output graph
        self.SAVE_PATH = "" #  Path of saved graph
        self.isNumericMode = False
        self.setWindowTitle('CSV analyzer')
        #Graph area setting
        self.fig = Figure()
        self.ax1 = self.fig.add_subplot(111)
        self.canv = FigureCanvas(self.fig)
        self.canv.setSizePolicy(Qw.QSizePolicy.Expanding, Qw.QSizePolicy.Expanding)
        self.canv.updateGeometry()
        self.layout = Qw.QGridLayout(self.ui.canvas)
        self.layout.addWidget(self.canv)
        self.ui.cmb_cmap.addItems(cmocean.cm.cmap_d.keys())
        self.PLOT_TYPE = Csviwer.SCATTER
        if data == None:
            pass
        else:
            self.loadData(data)


    def onStringChanged(self,value):
        # Log #--------------
        date_log = "<span style=\" font-size:13pt; font-weight:600; color:#8178FF;\" >"+"#"
        date_log += datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        date_log += "</span>" + "\n"
        self.ui.logbox.append(date_log)
        lexer = pygments.lexers.get_lexer_by_name('python3')
        formatter = pygments.formatters.get_formatter_by_name('html')
        html = pygments.highlight(value,lexer,formatter)
        self.ui.logbox.document().setDefaultStyleSheet(pygments.formatters.HtmlFormatter(style=Csviwer.STYLE).get_style_defs('.highlight'))
        self.ui.logbox.append(html)

        self.ui.logbox.moveCursor(Qg.QTextCursor.End)

    def loadData(self,data): #import csv file path
        # import CSV
        if type(data) == None:
            return
        self.ui.textbox_csvPath.setText("")
        # self.CSV_PATH = path
        self.csv = data
        self.csv["Row_INDEX_"] = np.linspace(1,len(self.csv),len(self.csv))
        self.data = data
        self.data["Row_INDEX_"] = np.linspace(1,len(self.data),len(self.data))
        # set Table
        model = PandasModel(self.csv)
        self.ui.table_summary.setModel(model)
        #==================
        # Init Tool bar
        #==================
        self.ui.frame_graph.setEnabled(True)
        self.ui.cmb_sort.setEnabled(False)
        self.ui.cmb_subsort.setEnabled(False)
        self.ui.cmb_subsubsort.setEnabled(False)
        self.HEADER_LIST = self.csv.columns
        self.ui.cmb_color.clear()
        self.ui.cmb_subcolor.clear()
        self.ui.cmb_subsubcolor.clear()
        self.ui.cmb_x.clear()
        self.ui.cmb_y.clear()
        self.ui.cmb_color.addItem("None_")
        self.ui.cmb_subcolor.addItem("None_")
        self.ui.cmb_subsubcolor.addItem("None_") 
        #==================
        # add header name into lists
        #==================
        for i,item in enumerate(self.HEADER_LIST):
            self.ui.cmb_color.addItem(item)
            self.ui.cmb_subcolor.addItem(item)
            self.ui.cmb_subsubcolor.addItem(item)
            self.ui.cmb_x.addItem(item)
            self.ui.cmb_y.addItem(item)
            # add only numeric data into X and Y axis lists
            isNumeric = True
            for comp in self.csv[item]:
                if isinstance(comp,str):
                    isNumeric = False
                    break
            if isNumeric:
                self.NUMERIC_HEADER_LIST.append(item)
        self.setXaxis()
        self.setYaxis()

    def readcsv(self): #import csv file path
        # import CSV
        path = self.openFile()
        if path == '':
            return
        self.ui.textbox_csvPath.setText(path)
        self.CSV_PATH = path
        self.csv = pd.read_csv(path)
        self.csv["Row_INDEX_"] = np.linspace(1,len(self.csv),len(self.csv))
        self.data = pd.read_csv(path)
        self.data["Row_INDEX_"] = np.linspace(1,len(self.data),len(self.data))
        # set Table
        model = PandasModel(self.csv)
        self.ui.table_summary.setModel(model)
        #==================
        # Init Tool bar
        #==================
        self.ui.frame_graph.setEnabled(True)
        self.ui.cmb_sort.setEnabled(False)
        self.ui.cmb_subsort.setEnabled(False)
        self.ui.cmb_subsubsort.setEnabled(False)
        self.HEADER_LIST = self.csv.columns
        self.ui.cmb_color.clear()
        self.ui.cmb_subcolor.clear()
        self.ui.cmb_subsubcolor.clear()
        self.ui.cmb_x.clear()
        self.ui.cmb_y.clear()
        self.ui.cmb_color.addItem("None_")
        self.ui.cmb_subcolor.addItem("None_")
        self.ui.cmb_subsubcolor.addItem("None_") 
        #==================
        # add header name into lists
        #==================
        for i,item in enumerate(self.HEADER_LIST):
            self.ui.cmb_color.addItem(item)
            self.ui.cmb_subcolor.addItem(item)
            self.ui.cmb_subsubcolor.addItem(item)
            self.ui.cmb_x.addItem(item)
            self.ui.cmb_y.addItem(item)
            # add only numeric data into X and Y axis lists
            isNumeric = True
            for comp in self.csv[item]:
                if isinstance(comp,str):
                    isNumeric = False
                    break
            if isNumeric:
                self.NUMERIC_HEADER_LIST.append(item)
        self.setXaxis()
        self.setYaxis()
                

    def setPlotType(self):
        self.PLOT_TYPE = self.ui.cmb_plot.currentIndex()
        if self.PLOT_TYPE == Csviwer.HISTGRAM: #Histogram
            # self.ui.cmb_x.clear()
            self.ui.cmb_y.setEnabled(False)
            # for i,item in enumerate(self.NUMERIC_HEADER_LIST):
                # self.ui.cmb_x.addItem(item)
        elif self.PLOT_TYPE == Csviwer.SCATTER:
            # self.ui.cmb_x.clear()
            # self.ui.cmb_y.clear()
            # self.ui.cmb_x.setEnabled(True)
            self.ui.cmb_y.setEnabled(True)
            # for i,item in enumerate(self.NUMERIC_HEADER_LIST):
                # self.ui.cmb_x.addItem(item)
                # self.ui.cmb_y.addItem(item)
        elif self.PLOT_TYPE == Csviwer.DENSITY:
            # self.ui.cmb_x.clear()
            # self.ui.cmb_y.clear()
            # self.ui.cmb_x.setEnabled(True)
            self.ui.cmb_y.setEnabled(True)
            # for i,item in enumerate(self.NUMERIC_HEADER_LIST):
                # self.ui.cmb_x.addItem(item)
                # self.ui.cmb_y.addItem(item)
        elif self.PLOT_TYPE == Csviwer.LINE:
            # self.ui.cmb_x.clear()
            # self.ui.cmb_y.clear()
            # self.ui.cmb_x.setEnabled(True)
            self.ui.cmb_y.setEnabled(True)
            # for i,item in enumerate(self.NUMERIC_HEADER_LIST):
                # self.ui.cmb_x.addItem(item)
                # self.ui.cmb_y.addItem(item)
        elif self.PLOT_TYPE == Csviwer.BOXPLOT:
            # self.ui.cmb_x.clear()
            # self.ui.cmb_y.clear()
            # self.ui.cmb_x.setEnabled(True)
            self.ui.cmb_y.setEnabled(True)
            # for i,item in enumerate(self.HEADER_LIST):
                # self.ui.cmb_x.addItem(item)
                # self.ui.cmb_y.addItem(item)
        # self.ui.cmb_x.setCurrentIndex(0)
        # self.ui.cmb_y.setCurrentIndex(1)

    def openFile(self): # select csv file
        filePath, _ = Qw.QFileDialog.getOpenFileName(self, "Open File",
                self.CSV_PATH, "csv files (*.csv)")
        return filePath

    def setXaxis(self):
        self.x_var = str(self.ui.cmb_x.currentText())
        if self.x_var in self.NUMERIC_HEADER_LIST:
            self.ax1.set_xlim( min(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan).dropna()) - abs(min(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan).dropna())/10), max(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan).dropna()) + abs(max(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan).dropna())/10) )
            self.ui.dsb_xmin.setEnabled(True); self.ui.dsb_xmax.setEnabled(True)
            self.ui.dsb_xmin.setRange(-np.inf,np.inf); self.ui.dsb_xmax.setRange(-np.inf,np.inf)
            self.ui.dsb_xmin.setValue( min(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan).dropna()) - abs(min(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan).dropna())/10) )
            self.ui.dsb_xmax.setValue( max(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan).dropna()) + abs(max(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan).dropna())/10) )
        else:
            self.ui.dsb_xmin.setEnabled(False); self.ui.dsb_xmax.setEnabled(False)
            self.ui.dsb_xmin.setRange(0,0); self.ui.dsb_xmax.setRange(0,0)
    def setYaxis(self):
        self.y_var = str(self.ui.cmb_y.currentText())
        if self.y_var in self.NUMERIC_HEADER_LIST:
            self.ax1.set_ylim( min(self.csv[self.y_var].replace([np.inf, -np.inf], np.nan).dropna()) - abs(min(self.csv[self.y_var].replace([np.inf, -np.inf], np.nan).dropna())/10), max(self.csv[self.y_var].replace([np.inf, -np.inf], np.nan).dropna()) + abs(max(self.csv[self.y_var].replace([np.inf, -np.inf], np.nan).dropna())/10) )
            self.ui.dsb_ymin.setEnabled(True); self.ui.dsb_ymax.setEnabled(True)
            self.ui.dsb_ymin.setRange(-np.inf,np.inf); self.ui.dsb_ymax.setRange(-np.inf,np.inf)
            self.ui.dsb_ymin.setValue( min(self.csv[self.y_var].replace([np.inf, -np.inf], np.nan).dropna()) - abs(min(self.csv[self.y_var].replace([np.inf, -np.inf], np.nan).dropna())/10) )
            self.ui.dsb_ymax.setValue( max(self.csv[self.y_var].replace([np.inf, -np.inf], np.nan).dropna()) + abs(max(self.csv[self.y_var].replace([np.inf, -np.inf], np.nan).dropna())/10) )
        else:
            self.ui.dsb_ymin.setEnabled(False); self.ui.dsb_ymax.setEnabled(False)
            self.ui.dsb_ymin.setRange(0,0); self.ui.dsb_ymax.setRange(0,0)

    def useColorMapI(self):
        pass
    def useColorMapII(self):
        pass
    def useColorMapIII(self):
        pass

    def setColor(self):
        ind = self.ui.cmb_color.currentIndex()
        tex = str(self.ui.cmb_color.currentText())
        self.color_var = tex
        if ind > 0:
            # self.color_var = tex
            # self.group_var = self.color_var
            isNumeric = True
            # isInteger = False
            for comp in self.csv[self.color_var]:
                if isinstance(comp,str):
                    isNumeric = False
                    break
            if isNumeric:
                self.ui.cmb_sort.clear()
                self.ui.cmb_sort.setEnabled(False)
                self.isNumericMode = True
            else:
                self.isNumericMode = False
                self.ui.cmb_sort.setEnabled(True)
                self.ui.cmb_subcolor.setEnabled(True)
                self.ui.cmb_subsort.setEnabled(True)
                self.ui.cmb_sort.clear()
                self.ui.cmb_sort.addItem("All_")
                sort_list = pd.unique(self.csv[self.color_var])
                for i,sort_item in enumerate(sort_list):
                    self.ui.cmb_sort.addItem(str(sort_item))
        else:
            # self.color_var = tex
            # self.group_var = self.color_var
            self.ui.cmb_sort.clear()
            self.ui.cmb_sort.setEnabled(False)
            self.ui.cmb_subcolor.setEnabled(False)
            self.ui.cmb_subsort.setEnabled(False)
            self.ui.cmb_subsubcolor.setEnabled(False)
            self.ui.cmb_subsubsort.setEnabled(False)

    def setSort(self):
        ind = self.ui.cmb_sort.currentIndex()
        tex = self.ui.cmb_sort.currentText()
        if ind > 0:
            self.ui.cmb_subcolor.setEnabled(True)
            self.ui.cmb_subsort.setEnabled(True)
            self.data = self.csv.loc[self.csv[self.color_var]==tex]
        else:
            self.ui.cmb_subcolor.setEnabled(False)
            self.ui.cmb_subsort.setEnabled(False)
            self.ui.cmb_subsubcolor.setEnabled(False)
            self.ui.cmb_subsubsort.setEnabled(False)
            self.data = self.csv
        model = PandasModel(self.data)
        self.ui.table_sorted.setModel(model)   

    def setSubColor(self):
        ind = self.ui.cmb_subcolor.currentIndex()
        tex = self.ui.cmb_subcolor.currentText()
        self.subcolor_var = tex
        if ind > 0:
            # self.subcolor_var = tex
            # self.group_var = self.subcolor_var
            isNumeric = True
            # isInteger = False
            for comp in self.data[self.subcolor_var]:
                if isinstance(comp,str):
                    isNumeric = False
                    break
            if isNumeric:
                self.ui.cmb_subsort.clear()
                self.ui.cmb_subsort.setEnabled(False)
                self.isNumericMode = True
            else:
                self.ui.cmb_subsort.setEnabled(True)
                self.ui.cmb_subsort.clear()
                self.ui.cmb_subsort.addItem("All_")
                sort_list = pd.unique(self.csv[self.subcolor_var])
                for i,sort_item in enumerate(sort_list):
                    self.ui.cmb_subsort.addItem(str(sort_item))
        else:
            # self.subcolor_var = tex
            # self.group_var = self.color_var
            self.ui.cmb_subsort.clear()
            self.ui.cmb_subsort.setEnabled(False)


    def setSubSort(self):
        ind = self.ui.cmb_subsort.currentIndex()
        tex = str(self.ui.cmb_subsort.currentText())
        if ind > 0:
            self.ui.cmb_subsubcolor.setEnabled(True)
            self.ui.cmb_subsubsort.setEnabled(True)
            data_temp = self.csv.loc[self.csv[self.color_var]==self.ui.cmb_sort.currentText()]
            self.data = data_temp.loc[data_temp[self.subcolor_var]==tex]
        else:
            self.ui.cmb_subsubcolor.setEnabled(False)
            self.ui.cmb_subsubsort.setEnabled(False)
            self.data = self.csv.loc[self.csv[self.color_var]==self.ui.cmb_sort.currentText()]
        model = PandasModel(self.data)
        self.ui.table_sorted.setModel(model)   

    def setSubsubColor(self):
        ind = self.ui.cmb_subsubcolor.currentIndex()
        tex = str(self.ui.cmb_subsubcolor.currentText())
        self.subsubcolor_var = tex
        if ind > 0:
            # self.group_var = self.subsubcolor_var
            isNumeric = True
            # isInteger = False
            for comp in self.data[ self.subsubcolor_var]:
                if isinstance(comp,str):
                    isNumeric = False
                    break
            if isNumeric:
                self.ui.cmb_subsubsort.clear()
                self.ui.cmb_subsubsort.setEnabled(False)
                self.isNumericMode = True
            else:
                self.ui.cmb_subsubsort.setEnabled(True)
                self.ui.cmb_subsubsort.clear()
                self.ui.cmb_subsubsort.addItem("All_")
                sort_list = pd.unique(self.csv[self.subsubcolor_var])
                for i,sort_item in enumerate(sort_list):
                    self.ui.cmb_subsubsort.addItem(str(sort_item))
        else:
            # self.subsubcolor_var = "None_"
            # self.group_var = self.subcolor_var
            self.ui.cmb_subsubsort.clear()
            self.ui.cmb_subsubsort.setEnabled(False)

    def setSubsubSort(self):
        ind = self.ui.cmb_subsubsort.currentIndex()
        tex = str(self.ui.cmb_subsubsort.currentText())
        if ind > 0:
            data_temp = self.csv.loc[self.csv[self.color_var]==self.ui.cmb_sort.currentText()]
            data_temp = data_temp.loc[data_temp[self.subcolor_var]==self.ui.cmb_subsort.currentText()]
            self.data = data_temp.loc[data_temp[self.subsubcolor_var]==tex]
        else:
            data_temp = self.csv.loc[self.csv[self.color_var]==self.ui.cmb_sort.currentText()]
            self.data = data_temp.loc[data_temp[self.subcolor_var]==self.ui.cmb_subsort.currentText()]
        model = PandasModel(self.data)
        self.ui.table_sorted.setModel(model)


    def checkPlot(self):
        pass

    

    def graphDraw(self):
        try:
           self.graphDraw_nonNumeric_Syntax()
        except ValueError as e:
            self.fig.clf()
            self.ax1.clear()
            self.ax1 = self.fig.add_subplot(111)
            self.ax1.text(x = 0.1, y= 0.5, s='ValueError'+'\n'+'Please check your axes setting or original data')
            self.fig.canvas.draw_idle()
            self.ui.tab_pca.setCurrentIndex(2)
        
        # if self.isNumericMode:
        #     self.graphDraw_Numeric()
        # else:
        #     self.graphDraw_nonNumeric()

    def graphDraw_nonNumeric(self):
        # Syntax Coloring Setting #--------------------------
        
        # Log #-----------------------
        File_log_str = '<div style=\" color:white \" >'
        File_log_str += '<span style=\" font-size:13pt; font-weight:600; color:#7F7F7F;\" >'
        File_log_str += '#- Import CSV as DataFrame ---------- ' + '\n'
        File_log_str += '</span>'
        File_log_str += '<p>' + 'FILE_PATH = <span style=\"color:yellow\">\'' + str(self.CSV_PATH) + '\'' + '</span>' + '</p>'
        File_log_str += '<p>' + 'DATA = pd.<span style=\"color:deepskyblue\">read_csv</span>(FILE_PATH)' + '</p>'
        File_log_str += '<span style=\" font-size:13pt; font-weight:600; color:#7F7F7F;\" >'
        File_log_str += '#- Axes Setting ---------- '
        File_log_str += '</span>'
        File_log_str += '<p>' + '<span style=\"color:white\">' + 'fig, ax = plt.<span style=\"color:deepskyblue\">subplots</span>()' + '</span>' + '</p>'
        # ----------------------------

        #- plot initial setting -------------------------------------
        SCATTER = 0
        DENSITY = 1
        HISTGRAM = 2
        LINE = 3
        BOXPLOT = 4

        ALL_SORT = 0

        colors=["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]
        # marker_list = [  "o", ",", "^", "v", "*", "<", ">", "1", ".", "2", "3","4", "8", "s", "p", "h", "H", "+", "x", "D","d", "|", "_", "None", None, "", "$x$","$\\alpha$", "$\\beta$", "$\\gamma$"]
        # marker_list = [  "o", ",", "^", "v", "*", "<", ">", "1","s", "p", "h", "H", "+", "x", "D","d", "|", "_", "None", None, "", "$x$","$\\alpha$", "$\\beta$", "$\\gamma$"".", "2", "3","4", "8"]
        marker_list = [ 'o', 'v', '^', '<', '>', '8', 's', 'p', '*', 'h', 'H', 'D', 'd', 'P', 'X' ]
        edge_color = 'black'
        edge_width = 0.0
        # Log #-----------------------
        # File_log_str += 'colors=["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' +'\n'
        # File_log_str += '[ "o", "v", "^", "<", ">", "8", "s", "p", "*", "h", "H", "D", "d", "P", "X" ]' +'\n'
        # File_log_str += 'edge_color = "black"' +'\n'
        # File_log_str += 'edge_width = 0.0' +'\n'
        # ----------------------------

        # cmap_list = ["winter","autumn","summer","spring","pink","Wistia"]
        cmap_list = list(matplotlib.cm.cmap_d.keys())
        cmap = self.ui.cmb_cmap.currentText()
        alpha = self.ui.dsb_alpha.value()
        bins_num = self.ui.spb_bins.value()
        hist_alpha = self.ui.dsb_alpha.value()
        clen = len( colors )
        mlen = len( marker_list )
        cmaplen = len( cmap_list )
        marker_size = self.ui.dsb_markerSize.value()
        self.fig.clf()
        self.ax1.clear()
        self.ax1 = self.fig.add_subplot(111)
        titleText = self.ui.text_title.text()
        if titleText != '':
            self.ax1.set_title(str(titleText))
            # Log #-----------------------
            File_log_str += '<p>' + 'ax.<span style=\"color:deepskyblue\">set_title</span>( "' + str(titleText) + '")' + '</p>'
            # ----------------------------
        self.ax1.set_xlabel( self.x_var )
        # Log #-----------------------
        File_log_str += '<p>' + 'ax.<span style=\"color:deepskyblue\">set_xlabel</span>( "' + str(self.x_var) + '")' + '</p>'
        # ----------------------------
        if self.PLOT_TYPE != HISTGRAM: 
            self.ax1.set_ylabel( self.y_var )
            # Log #-----------------------
            File_log_str += '<p>' + 'ax.<span style=\"color:deepskyblue\">set_ylabel</span>( "' + str(self.y_var) + '" )' + '</p>'
            # ----------------------------
        elif self.PLOT_TYPE == HISTGRAM:
            self.ax1.set_ylabel('Frequency')
            # Log #-----------------------
            File_log_str += '<p>' + 'ax.<span style=\"color:deepskyblue\">set_ylabel</span>( "Frequency" )' + '</p>'
            # ----------------------------

        # x axis setting
        if self.PLOT_TYPE != HISTGRAM and self.ui.cb_logx.isChecked(): # Hist
            self.ax1.set_xscale('log')
            # Log #-----------------------
            File_log_str += '<p>' + 'ax.<span style=\"color:deepskyblue\">set_xscale</span>( \'log\' )' + '</p>'
            # ----------------------------
        if self.x_var in self.NUMERIC_HEADER_LIST:
            xmax = 0
            if self.ui.dsb_xmax.value() < self.ui.dsb_xmin.value():
                xmax = self.ui.dsb_xmin.value()
            else:
                xmax = self.ui.dsb_xmax.value()
            self.ax1.set_xlim( self.ui.dsb_xmin.value() , xmax )
            # Log #-----------------------
            # File_log_str += '<p>' + 'ax.<span style=\"color:deepskyblue\">set_xlim</span>( min(DATA[\'' + str(self.x_var) + '\'].replace([np.inf, -np.inf], np.nan ).dropna() ) - abs( min(DATA[\'' + str(self.x_var) + '\'].replace([np.inf, -np.inf], np.nan ).dropna() )/10), max(DATA[\''+str(self.x_var)+'\'].replace([np.inf, -np.inf], np.nan).dropna()) + abs(max(DATA[\''+str(self.x_var)+'\'].replace([np.inf, -np.inf], np.nan).dropna())/10)  )' +'</p>'
            File_log_str += '<p>' + 'ax.<span style=\"color:deepskyblue\">set_xlim</span>(<span style=\"color:deepskyblue\">min</span>(DATA[\'' + str(self.x_var) + '\'].replace([np.inf, -np.inf], np.nan ).dropna() ) - abs( min(DATA[\'' + str(self.x_var) + '\'].replace([np.inf, -np.inf], np.nan ).dropna() )/10), max(DATA[\''+str(self.x_var)+'\'].replace([np.inf, -np.inf], np.nan).dropna()) + abs(max(DATA[\''+str(self.x_var)+'\'].replace([np.inf, -np.inf], np.nan).dropna())/10)  )' +'</p>'
            # ----------------------------
        # y axis setting
        if self.PLOT_TYPE != HISTGRAM: # Hist
            if self.ui.cb_logy.isChecked():
                self.ax1.set_yscale('log')
                # Log #-----------------------
                File_log_str += '<p>' + 'ax.<span style=\"color:deepskyblue\">set_yscale</span>( \'log\' )' + '</p>'
                # ----------------------------
        if self.y_var in self.NUMERIC_HEADER_LIST and self.PLOT_TYPE != HISTGRAM:
            ymax = 0
            if self.ui.dsb_ymax.value() < self.ui.dsb_ymin.value():
                ymax = self.ui.dsb_ymin.value()
            else:
                ymax = self.ui.dsb_ymax.value()
            self.ax1.set_ylim( self.ui.dsb_ymin.value() , ymax )
            # Log #-----------------------
            File_log_str += '<p>' + 'ax.<span style=\"color:deepskyblue\">set_ylim</span>( <span style=\"color:deepskyblue\">min</span>(DATA[\''+str(self.y_var) + '\'].<span style=\"color:deepskyblue\">replace</span>([np.inf, -np.inf], np.nan ).<span style=\"color:deepskyblue\">dropna</span>() ) - abs( <span style=\"color:deepskyblue\">min</span>(DATA[\'' + str(self.y_var) + '\'].<span style=\"color:deepskyblue\">replace</span>([np.inf, -np.inf], np.nan ).<span style=\"color:deepskyblue\">dropna</span>() )/10), <span style=\"color:deepskyblue\">max</span>(DATA[\''+str(self.y_var)+'\'].<span style=\"color:deepskyblue\">replace</span>([np.inf, -np.inf], np.nan).<span style=\"color:deepskyblue\">dropna</span>()) + <span style=\"color:deepskyblue\">abs</span>(<span style=\"color:deepskyblue\">max</span>(DATA[\''+str(self.y_var)+'\'].<span style=\"color:deepskyblue\">replace</span>([np.inf, -np.inf], np.nan).<span style=\"color:deepskyblue\">dropna</span>())/10)  )' + '</p>'
            # ----------------------------
        # DATA PLOT
        #========================================================
        File_log_str += '<span style=\" font-size:13pt; font-weight:600; color:#7F7F7F;\" >'
        File_log_str += '#- PLOT ------------------ '
        File_log_str += '</span>'
        if self.color_var == "None_": # simple plot (scatter)
            if self.PLOT_TYPE == SCATTER:
                self.ax1.scatter(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan), self.csv[self.y_var].replace([np.inf, -np.inf], np.nan), s = marker_size, alpha = alpha,edgecolor=edge_color,linewidth=edge_width)
                # Log #-----------------------
                File_log_str += '<p>' + 'ax.scatter(DATA["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), DATA["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), s = '+str(marker_size)+', alpha ='+str(alpha)+',edgecolor="' + str(edge_color)+'",linewidth= ' + str(edge_width) +')' + '</p>'
                # ----------------------------
            elif self.PLOT_TYPE == DENSITY: #density
                if len(self.csv) != 0:
                    sns.kdeplot( self.csv[self.x_var], self.csv[self.y_var], ax = self.ax1, shade=True, cbar = True, cmap = "cmo."+cmap  )
                    # Log #-----------------------
                    File_log_str += '<p>' + 'sns.kdeplot(DATA["' + str(self.x_var) + '"], DATA["' + str(self.y_var) + '"], ax = ax, shade = True, cbar = True, cmap = "cmo." + "'+str(cmap)+'" ) ' + '</p>'
                    # ----------------------------
            elif self.PLOT_TYPE == HISTGRAM: #Histgoram
                self.ax1.hist(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan).dropna(), bins = bins_num, alpha = alpha, weights = np.zeros_like(self.csv[self.x_var])+1./self.csv[self.x_var].size)
                # Log #-----------------------
                File_log_str += '<p>' + 'ax.hist(DATA["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(DATA["'+str(self.x_var)+'"])+1./DATA["' + str(self.x_var) + '"].size ' + ')' + '</p>'
                # ----------------------------
            elif self.PLOT_TYPE == LINE: # line
                self.ax1.plot(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan), self.csv[self.y_var].replace([np.inf, -np.inf], np.nan), linewidth = marker_size, alpha = alpha, color = colors[0])
                # Log #-----------------------
                File_log_str += '<p>' + 'ax.plot( DATA["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), DATA["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), linewidth = '+str(marker_size)+', alpha ='+str(alpha)+ ', color = "' + str(colors[0]) + '" )' + '</p>'
                # ----------------------------
            elif self.PLOT_TYPE == BOXPLOT:
                data = self.csv.replace([np.inf, -np.inf], np.nan).dropna()
                sns.boxplot(y=self.y_var,x=self.x_var,data=data,ax=self.ax1)
                # print(type(self.ax1))
                # Log #-----------------------
                File_log_str += '<p>' + 'ax = sns.boxplot( x = "'+str(self.x_var)+'", y = "'+str(self.y_var)+'", data=DATA.replace([np.inf, -np.inf], np.nan).dropna() )' + '</p>'
                # ----------------------------
        else:
            isNumeric = True
            for comp in self.csv[self.color_var]:
                if isinstance(comp,str):
                    isNumeric = False
                    break
            if self.ui.cmb_sort.currentIndex() == ALL_SORT: # use discrete colors and plot all
                for i, value in enumerate(pd.unique(self.csv[self.color_var])):
                    color_index = i%clen
                    marker_index = i%mlen
                    cmap_index = i%cmaplen
                    data = self.csv.loc[ self.csv[self.color_var] == value ]
                    # scatter graph
                    if self.PLOT_TYPE == SCATTER: # scatter
                        self.ax1.scatter(data[self.x_var].replace([np.inf, -np.inf], np.nan), data[self.y_var].replace([np.inf, -np.inf], np.nan) , color = colors[color_index], marker = marker_list[marker_index], alpha = alpha, s = marker_size, label = value)
                    elif self.PLOT_TYPE == DENSITY: # density 
                        if len(data) != 0:
                            temp_clr = [colors[color_index],colors[color_index],colors[color_index]]
                            values = range(len(temp_clr))
                            vmax = np.ceil(np.max(values))
                            clr_list = []
                            for v, c in zip(values, temp_clr):
                                clr_list.append( ( v/ vmax, c) )
                            cmap = LinearSegmentedColormap.from_list('custom_cmap', clr_list)
                            sns.kdeplot( data[self.x_var].replace([np.inf, -np.inf], np.nan), data[self.y_var].replace([np.inf, -np.inf], np.nan),shade=False, ax = self.ax1, cmap = cmap )
                            # cset = kde2dgraph(self.ax1, data[self.x_var], data[self.y_var], min(self.csv[self.x_var]),max(self.csv[self.x_var]),min(self.csv[self.y_var]),max(self.csv[self.y_var]),cmap_list[cmap_index])
                    elif self.PLOT_TYPE == HISTGRAM: # Histogram
                        self.ax1.hist(data[self.x_var], bins = bins_num, alpha = hist_alpha, weights = np.zeros_like(data[self.x_var])+1./data[self.x_var].size,label = value)
                    elif self.PLOT_TYPE == LINE:
                        self.ax1.plot(data[self.x_var].replace([np.inf, -np.inf], np.nan), data[self.y_var].replace([np.inf, -np.inf], np.nan) , color = colors[color_index], alpha = alpha, linewidth = marker_size, label = value)
                if self.PLOT_TYPE == BOXPLOT:
                    data = self.csv.replace([np.inf, -np.inf], np.nan).dropna()
                    sns.boxplot(y=self.y_var, x=self.x_var, hue = self.color_var, data=data, ax=self.ax1)
                # Log #-----------------------
                # File_log_str += '<span style=\" font-size:13pt; font-weight:600; color:#7F7F7F;\" >'
                # File_log_str += '#- Lists of Colors and Markers ---------- ' + '\n'
                # File_log_str += '</span>'
                
                if self.PLOT_TYPE == BOXPLOT:
                    File_log_str += '<p>' +  'sns.boxplot( x = "' + str(self.x_var) + '", y = "' + str(self.y_var) + '", hue = "' + str(self.color_var) + '", data = DATA.replace([np.inf, -np.inf], np.nan).dropna(), ax = ax )' + '</p>'
                else:
                    File_log_str += '<p>' +  'for i, value in enumerate( pd.unique( DATA["' + str(self.color_var) + '"] ) ):' + '</p>'
                    File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'sub_data = DATA.loc[ DATA["' + str(self.color_var) + '"] == value ]' + '</p>'
                    if self.PLOT_TYPE == SCATTER:
                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '</p>'
                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'markers = [ "o", "v", "^", "<", ">", "8", "s", "p", "*", "h", "H", "D", "d", "P", "X" ]' + '</p>'
                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'c_index = i%len(colors)' + '</p>'
                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'm_index = i%len(markers)' + '</p>'
                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'ax.scatter( sub_data["'+ str(self.x_var) +'"].replace([np.inf, -np.inf], np.nan), sub_data["'+ str(self.y_var) +'"].replace([np.inf, -np.inf], np.nan), color = colors[c_index], marker = markers[m_index], alpha = '+str(alpha)+', s = '+str(marker_size)+', label = value)' + '</p>'
                    elif self.PLOT_TYPE == DENSITY:
                        # File_log_str += '<p>' +  '&nbsp;&nbsp;&nbsp;&nbsp;'+'cm_index = i%len(cmaps)' + '</p>'
                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '</p>'
                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'c_index = i%len(colors)' + '</p>'
                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'sns.kdeplot(sub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), sub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), shade = False, ax = ax, cmap = generate_cmap([colors[c_index],colors[c_index],colors[c_index]]) )' + '</p>'
                    elif self.PLOT_TYPE == HISTGRAM:
                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'ax.hist(sub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(sub_data["'+str(self.x_var)+'"])+1./sub_data["' + str(self.x_var) + '"].size ' + ')' + '</p>'
                    elif self.PLOT_TYPE == LINE:
                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '</p>'
                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'c_index = i%len(colors)' + '</p>'
                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'ax.plot( sub_data["'+ str(self.x_var) +'"].replace([np.inf, -np.inf], np.nan), sub_data["'+ str(self.y_var) +'"].replace([np.inf, -np.inf], np.nan), color = colors[c_index], alpha = '+str(alpha)+', linewidth = '+str(marker_size)+', label = value )' + '</p>'
                # ----------------------------
            else:  # Sorting by specific value
                value = self.ui.cmb_sort.currentIndex() - 1
                data = self.csv.loc[ self.csv[self.color_var] == pd.unique(self.csv[self.color_var])[value] ]
                # Log #-----------------------
                File_log_str += '<p>' + 'sub_data = DATA.loc[ DATA["' + str(self.color_var) + '"] == "'+str(pd.unique(self.csv[self.color_var])[value])+'"]' + '</p>'
                # ----------------------------
                if self.subcolor_var == 'None_': 
                    # scatter graph
                    if self.PLOT_TYPE == SCATTER:
                        self.ax1.scatter(data[self.x_var].replace([np.inf, -np.inf], np.nan), data[self.y_var].replace([np.inf, -np.inf], np.nan), alpha = alpha, s = marker_size, label = pd.unique(self.csv[self.color_var])[value])
                        # Log #-----------------------
                        File_log_str += '<p>' + 'ax.scatter(sub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), sub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), s = '+str(marker_size)+', alpha ='+str(alpha)+',edgecolor="' + str(edge_color)+'",linewidth= ' + str(edge_width) +')' + '</p>'
                        # ----------------------------
                    elif self.PLOT_TYPE == DENSITY: # Density plot (when x and y are the same, it stacks)
                        if len(data) != 2:
                            sns.kdeplot(self.ax1,data[self.x_var].replace([np.inf, -np.inf], np.nan),data[self.y_var].replace([np.inf, -np.inf], np.nan), shade=True, cbar = True, cmap = "cmo."+cmap )
                            # Log #-----------------------
                            File_log_str += '<p>' + 'sns.kdeplot(sub_data["' + str(self.x_var) + '"], sub_data["' + str(self.y_var) + '"], ax = ax, shade = True, cbar = True, cmap = "cmo." + "'+str(cmap)+'" ) ' + '</p>'
                            # ----------------------------
                    elif self.PLOT_TYPE == HISTGRAM:
                        self.ax1.hist(data[self.x_var], bins = bins_num, alpha = alpha, weights=np.zeros_like(data[self.x_var])+1./data[self.x_var].size,label = pd.unique(self.csv[self.color_var])[value])
                        # Log #-----------------------
                        File_log_str += '<p>' + 'ax.hist(sub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(sub_data["'+str(self.x_var)+'"])+1./sub_data["' + str(self.x_var) + '"].size ' + ')' + '</p>'
                        # ----------------------------
                    elif self.PLOT_TYPE == LINE:
                        self.ax1.plot(data[self.x_var].replace([np.inf, -np.inf], np.nan), data[self.y_var].replace([np.inf, -np.inf], np.nan), alpha = alpha, linewidth = marker_size, label = pd.unique(self.csv[self.color_var])[value])
                        # Log #-----------------------
                        File_log_str += '<p>' + 'ax.plot(sub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), sub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), linewidth = '+str(marker_size)+', alpha ='+str(alpha) + ')' + '</p>'
                        # ----------------------------
                    elif self.PLOT_TYPE == BOXPLOT:
                        sns.boxplot(y=self.y_var,x=self.x_var,data=data,ax=self.ax1)
                        # Log #-----------------------
                        File_log_str += '<p>' + 'ax = sns.boxplot( x = "'+str(self.x_var)+'", y = "'+str(self.y_var)+'", data=sub_data.replace([np.inf, -np.inf], np.nan).dropna() )' + '</p>'
                        # ----------------------------

                else:
                    if self.ui.cmb_subsort.currentIndex() == ALL_SORT: # use discrete colors and plot all
                        for i, value2 in enumerate(pd.unique(data[self.subcolor_var])):
                            color_index = i%clen
                            marker_index = i%mlen
                            cmap_index = i%cmaplen
                            data2 = data.loc[ data[self.subcolor_var] == value2 ]
                            # scatter graph
                            if self.PLOT_TYPE == SCATTER: 
                                self.ax1.scatter(data2[self.x_var].replace([np.inf, -np.inf], np.nan), data2[self.y_var].replace([np.inf, -np.inf], np.nan), color = colors[color_index], marker = marker_list[marker_index], alpha = alpha, s = marker_size, label = value2)
                            elif self.PLOT_TYPE == DENSITY: 
                                if len(data2) != 0:
                                    temp_clr = [colors[color_index],colors[color_index],colors[color_index]]
                                    values = range(len(temp_clr))
                                    vmax = np.ceil(np.max(values))
                                    clr_list = []
                                    for v, c in zip(values, temp_clr):
                                        clr_list.append( ( v/ vmax, c) )
                                    cmap = LinearSegmentedColormap.from_list('custom_cmap', clr_list)
                                    sns.kdeplot( data2[self.x_var].replace([np.inf, -np.inf], np.nan), data2[self.y_var].replace([np.inf, -np.inf], np.nan),shade=False, ax = self.ax1, cmap = cmap )
                                    # cset = kde2dgraph(self.ax1, data2[self.x_var], data2[self.y_var], min(self.csv[self.x_var]),max(self.csv[self.x_var]),min(self.csv[self.y_var]),max(self.csv[self.y_var]),cmap_list[cmap_index])
                            elif self.PLOT_TYPE == HISTGRAM:
                                self.ax1.hist(data2[self.x_var], bins=bins_num, alpha=hist_alpha, weights=np.zeros_like(data2[self.x_var])+1./data2[self.x_var].size, label = value2)
                            elif self.PLOT_TYPE == LINE:
                                self.ax1.plot(data2[self.x_var].replace([np.inf, -np.inf], np.nan), data2[self.y_var].replace([np.inf, -np.inf], np.nan), color = colors[color_index], alpha = alpha, linewidth = marker_size, label = value2)
                        if self.PLOT_TYPE == BOXPLOT:
                            sns.boxplot(y=self.y_var, x=self.x_var, hue = self.subcolor_var, data=data.replace([np.inf, -np.inf], np.nan).dropna(), ax=self.ax1)

                        # Log #-----------------------
                        # File_log_str += '<span style=\" font-size:13pt; font-weight:600; color:#7F7F7F;\" >'
                        # File_log_str += '#- Lists of Colors and Markers ---------- ' + '\n'
                        # File_log_str += '</span>'
                        # if self.PLOT_TYPE != DENSITY:
                        #     File_log_str += '<p>' +  'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '</p>'
                        #     File_log_str += '<p>' +  'markers = [ "o", "v", "^", "<", ">", "8", "s", "p", "*", "h", "H", "D", "d", "P", "X" ]' + '</p>'
                        # else:
                        #     File_log_str += '<p>' +  'cmaps = list(matplotlib.cm.cmap_d.keys())' + '</p>'
                        if self.PLOT_TYPE == BOXPLOT:
                            File_log_str += '<p>' +  'sns.boxplot( x = "' + str(self.x_var) + '", y = "' + str(self.y_var) + '", hue = "' + str(self.subcolor_var) + '", data = sub_data.replace([np.inf, -np.inf], np.nan).dropna(), ax = ax )' + '</p>'
                        else:
                            File_log_str += '<p>' +  'for i, value in enumerate( pd.unique( sub_data["' + str(self.subcolor_var) + '"] ) ):' + '</p>'
                            File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'subsub_data = sub_data.loc[ sub_data["' + str(self.subcolor_var) + '"] == value ]' + '</p>'
                            if self.PLOT_TYPE == SCATTER:
                                File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '</p>'
                                File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'markers = [ "o", "v", "^", "<", ">", "8", "s", "p", "*", "h", "H", "D", "d", "P", "X" ]' + '</p>'
                                File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'c_index = i%len(colors)' + '</p>'
                                File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'm_index = i%len(markers)' + '</p>'
                                File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'ax.scatter( subsub_data["'+ str(self.x_var) +'"].replace([np.inf, -np.inf], np.nan), subsub_data["'+ str(self.y_var) +'"].replace([np.inf, -np.inf], np.nan), color = colors[c_index], marker = markers[m_index], alpha = '+str(alpha)+', s = '+str(marker_size)+', label = value) )' + '</p>'
                            elif self.PLOT_TYPE == DENSITY:
                                File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '</p>'
                                File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'c_index = i%len(colors)' + '</p>'
                                File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'sns.kdeplot( subsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), subsub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), shade = False, ax = ax, cmap = generate_cmap([colors[c_index],colors[c_index],colors[c_index]]) )' + '</p>'
                                # File_log_str += '<p>' +  '&nbsp;&nbsp;&nbsp;&nbsp;'+'cset = kde2dgraph(ax, subsub_data["'+str(self.x_var)+'"], subsub_data["'+str(self.y_var)+'"], min(DATA["'+str(self.x_var)+'"]), max(DATA["'+str(self.x_var)+'"]),min(DATA["'+str(self.y_var)+'"]),max(DATA["'+str(self.y_var)+'"]),cmaps[cm_index])' + '</p>'
                            elif self.PLOT_TYPE == HISTGRAM:
                                # File_log_str += '<p>' +  '&nbsp;&nbsp;&nbsp;&nbsp;'+'c_index = i%len(colors)' + '</p>'
                                File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'ax.hist(subsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(subsub_data["'+str(self.x_var)+'"])+1./subsub_data["' + str(self.x_var) + '"].size ' + ')' + '</p>'
                            elif self.PLOT_TYPE == LINE:
                                File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '</p>'
                                File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'c_index = i%len(colors)' + '</p>'
                                File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'ax.plot( subsub_data["'+ str(self.x_var) +'"].replace([np.inf, -np.inf], np.nan), subsub_data["'+ str(self.y_var) +'"].replace([np.inf, -np.inf], np.nan), color = colors[c_index], alpha = '+str(alpha)+', linewidth = '+str(marker_size)+', label = value )' + '</p>'
                        # ----------------------------
                    else:
                        value2 = self.ui.cmb_subsort.currentIndex() - 1
                        data2 = data.loc[ data[ self.subcolor_var ] == pd.unique(self.csv[self.subcolor_var])[value2] ]
                        # Log #-----------------------
                        File_log_str += '<p>' + 'subsub_data = sub_data.loc[ sub_data["' + str(self.subcolor_var) + '"] == "'+str(pd.unique(self.csv[self.subcolor_var])[value2])+'"]' + '</p>'
                        # ----------------------------
                        if self.subsubcolor_var == 'None_':
                            if self.PLOT_TYPE == SCATTER:
                                self.ax1.scatter(data2[self.x_var].replace([np.inf, -np.inf], np.nan), data2[self.y_var].replace([np.inf, -np.inf], np.nan), alpha = alpha, s = marker_size, label = pd.unique(self.csv[self.subcolor_var])[value2])
                                # Log #-----------------------
                                File_log_str += '<p>' + 'ax.scatter(subsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), subsub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), s = '+str(marker_size)+', alpha ='+str(alpha)+',edgecolor="' + str(edge_color)+'",linewidth= ' + str(edge_width) +')' + '</p>'
                                # ----------------------------
                            elif self.PLOT_TYPE == DENSITY: # Density plot (when x and y are the same, it stacks)
                                if len(data2) != 0:
                                    sns.kdeplot(self.ax1,data2[self.x_var].replace([np.inf, -np.inf], np.nan),data2[self.y_var].replace([np.inf, -np.inf], np.nan), shade=True, cbar = True, cmap = "cmo."+cmap )
                                    # Log #-----------------------
                                    File_log_str += '<p>' + 'sns.kdeplot(subsub_data["' + str(self.x_var) + '"], subsub_data["' + str(self.y_var) + '"], ax = ax, shade = True, cbar = True, cmap = "cmo." + "'+str(cmap)+'" ) ' + '</p>'
                                    # ----------------------------
                                    # cfset = kde2dgraphfill(self.ax1,data2[self.x_var],data2[self.y_var],min(self.csv[self.x_var]),max(self.csv[self.x_var]),min(self.csv[self.y_var]),max(self.csv[self.y_var]))
                                    # cax = self.fig.add_axes([0.8, 0.2, 0.05, 0.5])
                                    # self.fig.colorbar(cfset,cax=cax,orientation='vertical')
                            elif self.PLOT_TYPE == HISTGRAM:
                                self.ax1.hist(data2[self.x_var], bins=bins_num, alpha=alpha, weights=np.zeros_like(data2[self.x_var])+1./data2[self.x_var].size, label = pd.unique(self.csv[self.subcolor_var])[value2])
                                # Log #-----------------------
                                File_log_str += '<p>' + 'ax.hist(subsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(subsub_data["'+str(self.x_var)+'"])+1./subsub_data["' + str(self.x_var) + '"].size ' + ')' + '</p>'
                                # ----------------------------
                            elif self.PLOT_TYPE == LINE:
                                self.ax1.plot(data2[self.x_var].replace([np.inf, -np.inf], np.nan), data2[self.y_var].replace([np.inf, -np.inf], np.nan), alpha = alpha, linewidth = marker_size, label = pd.unique(self.csv[self.subcolor_var])[value2])
                                # Log #-----------------------
                                File_log_str += '<p>' + 'ax.plot(subsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), subsub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), linewidth = '+str(marker_size)+', alpha ='+str(alpha) + ')' + '</p>'
                                # ----------------------------
                            elif self.PLOT_TYPE == BOXPLOT:
                                sns.boxplot(y=self.y_var,x=self.x_var,data=data2,ax=self.ax1)
                                # Log #-----------------------
                                File_log_str += '<p>' + 'ax = sns.boxplot( x = "'+str(self.x_var)+'", y = "'+str(self.y_var)+'", data=subsub_data.replace([np.inf, -np.inf], np.nan).dropna() )' + '</p>'
                                # ----------------------------
                        else:
                            if self.ui.cmb_subsubsort.currentIndex() == ALL_SORT: # use discrete colors and plot all
                                for i, value3 in enumerate(pd.unique(self.csv[self.subsubcolor_var])):
                                    color_index = i%clen
                                    marker_index = i%mlen
                                    cmap_index = i%cmaplen
                                    data3 = data2.loc[ data2[self.subsubcolor_var] == value3 ]
                                    # scatter graph
                                    if self.PLOT_TYPE == SCATTER: 
                                        self.ax1.scatter(data3[self.x_var].replace([np.inf, -np.inf], np.nan), data3[self.y_var].replace([np.inf, -np.inf], np.nan), color = colors[color_index], marker = marker_list[marker_index], alpha = alpha, s = marker_size, label = value3)
                                    elif self.PLOT_TYPE == DENSITY: 
                                        if len(data3) != 0:
                                            temp_clr = [colors[color_index],colors[color_index],colors[color_index]]
                                            values = range(len(temp_clr))
                                            vmax = np.ceil(np.max(values))
                                            clr_list = []
                                            for v, c in zip(values, temp_clr):
                                                clr_list.append( ( v/ vmax, c) )
                                            cmap = LinearSegmentedColormap.from_list('custom_cmap', clr_list)
                                            sns.kdeplot( data3[self.x_var].replace([np.inf, -np.inf], np.nan), data3[self.y_var].replace([np.inf, -np.inf], np.nan),shade=False, ax = self.ax1, cmap = cmap )
                                            # cset = kde2dgraph(self.ax1, data3[self.x_var], data3[self.y_var], min(self.csv[self.x_var]),max(self.csv[self.x_var]),min(self.csv[self.y_var]),max(self.csv[self.y_var]),cmap_list[cmap_index]) 
                                    elif self.PLOT_TYPE == HISTGRAM:
                                        self.ax1.hist(data3[self.x_var], bins=bins_num, alpha=hist_alpha, weights=np.zeros_like(data3[self.x_var])+1./data3[self.x_var].size, label = value3)
                                    elif self.PLOT_TYPE == LINE:
                                        self.ax1.plot(data3[self.x_var].replace([np.inf, -np.inf], np.nan), data3[self.y_var].replace([np.inf, -np.inf], np.nan), color = colors[color_index], alpha = alpha, linewidth = marker_size, label = value3)
                                if self.PLOT_TYPE == BOXPLOT:
                                    sns.boxplot(y=self.y_var, x=self.x_var, hue = self.subsubcolor_var, data=data2.replace([np.inf, -np.inf], np.nan).dropna(), ax=self.ax1)

                                # Log #-----------------------
                                # File_log_str += '<span style=\" font-size:13pt; font-weight:600; color:#7F7F7F;\" >'
                                # File_log_str += '#- Lists of Colors and Markers ---------- ' + '\n'
                                # File_log_str += '</span>'
                                # if self.PLOT_TYPE != DENSITY:
                                #     File_log_str += '<p>' +  'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '</p>'
                                #     File_log_str += '<p>' +  'markers = [ "o", "v", "^", "<", ">", "8", "s", "p", "*", "h", "H", "D", "d", "P", "X" ]' + '</p>'
                                # else:
                                #     File_log_str += '<p>' +  'cmaps = list(matplotlib.cm.cmap_d.keys())' + '</p>'
                                if self.PLOT_TYPE == BOXPLOT:
                                    File_log_str += '<p>' + 'sns.boxplot( x = "' + str(self.x_var) + '", y = "' + str(self.y_var) + '", hue = "' + str(self.subsubcolor_var) + '", data = subsub_data.replace([np.inf, -np.inf], np.nan).dropna(), ax = ax )' + '</p>'
                                else:
                                    File_log_str += '<p>' + 'for i, value in enumerate( pd.unique( subsub_data["' + str(self.subsubcolor_var) + '"] ) ):' + '</p>'
                                    File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'subsubsub_data = subsub_data.loc[ subsub_data["' + str(self.subsubcolor_var) + '"] == value ]' + '</p>'
                                    if self.PLOT_TYPE == SCATTER:
                                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '</p>'
                                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'markers = [ "o", "v", "^", "<", ">", "8", "s", "p", "*", "h", "H", "D", "d", "P", "X" ]' + '</p>'
                                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'c_index = i%len(colors)' + '</p>'
                                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'm_index = i%len(markers)' + '</p>'
                                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'ax.scatter( subsubsub_data["'+ str(self.x_var) +'"].replace([np.inf, -np.inf], np.nan), subsubsub_data["'+ str(self.y_var) +'"].replace([np.inf, -np.inf], np.nan), color = colors[c_index], marker = markers[m_index], alpha = '+str(alpha)+', s = '+str(marker_size)+', label = value) )' + '</p>'
                                    elif self.PLOT_TYPE == DENSITY:
                                        # File_log_str += '<p>' +  '&nbsp;&nbsp;&nbsp;&nbsp;'+'cm_index = i%len(cmaps)' + '</p>'
                                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '</p>'
                                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'c_index = i%len(colors)' + '</p>'
                                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'sns.kdeplot( subsubsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), subsubsub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), shade = False, ax = ax, cmap = generate_cmap([colors[c_index],colors[c_index],colors[c_index]]) )' + '</p>'
                                        # File_log_str += '<p>' +  '&nbsp;&nbsp;&nbsp;&nbsp;'+'cset = kde2dgraph(ax, subsubsub_data["'+str(self.x_var)+'"], subsubsub_data["'+str(self.y_var)+'"], min(DATA["'+str(self.x_var)+'"]), max(DATA["'+str(self.x_var)+'"]),min(DATA["'+str(self.y_var)+'"]),max(DATA["'+str(self.y_var)+'"]),cmaps[cm_index])' + '</p>'
                                    elif self.PLOT_TYPE == HISTGRAM:
                                        # File_log_str += '<p>' +  'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '</p>'
                                        # File_log_str += '<p>' +  '&nbsp;&nbsp;&nbsp;&nbsp;'+'c_index = i%len(colors)' + '</p>'
                                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'ax.hist(subsubsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(subsubsub_data["'+str(self.x_var)+'"])+1./subsubsub_data["' + str(self.x_var) + '"].size ' + ')' + '</p>'
                                    elif self.PLOT_TYPE == LINE:
                                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '</p>'
                                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'c_index = i%len(colors)' + '</p>'
                                        File_log_str += '<p>' + '&nbsp;&nbsp;&nbsp;&nbsp;' + 'ax.plot( subsubsub_data["'+ str(self.x_var) +'"].replace([np.inf, -np.inf], np.nan), subsubsub_data["'+ str(self.y_var) +'"].replace([np.inf, -np.inf], np.nan), color = colors[c_index], alpha = '+str(alpha)+', linewidth = '+str(marker_size)+', label = value )' + '</p>'
                                # ----------------------------    
                            else:
                                value3 = self.ui.cmb_subsubsort.currentIndex() - 1
                                data3 = data2.loc[ data2[ self.subsubcolor_var ] == pd.unique(self.csv[self.subsubcolor_var])[value3] ]
                                # Log #-----------------------
                                File_log_str += '<p>' + 'subsubsub_data = subsub_data.loc[ subsub_data["' + str(self.subsubcolor_var) + '"] == "'+str(pd.unique(self.csv[self.subsubcolor_var])[value3])+'"]' + '</p>'
                                # ----------------------------
                                # scatter graph
                                if self.PLOT_TYPE == SCATTER:
                                    self.ax1.scatter(data3[self.x_var].replace([np.inf, -np.inf], np.nan), data3[self.y_var].replace([np.inf, -np.inf], np.nan), alpha = alpha, s = marker_size, label = pd.unique(self.csv[self.subsubcolor_var])[value3])
                                    # Log #-----------------------
                                    File_log_str += '<p>' + 'ax.scatter(subsubsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), subsubsub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), s = '+str(marker_size)+', alpha ='+str(alpha)+',edgecolor="' + str(edge_color)+'",linewidth= ' + str(edge_width) +')' + '</p>'
                                    # ----------------------------
                                elif self.PLOT_TYPE == DENSITY: # Density plot (when x and y are the same, it stacks)
                                    if len(data3) != 0:
                                        sns.kdeplot(self.ax1,data3[self.x_var].replace([np.inf, -np.inf], np.nan),data3[self.y_var].replace([np.inf, -np.inf], np.nan), shade=True, cbar = True, cmap = "cmo."+cmap )
                                        # Log #-----------------------
                                        File_log_str += '<p>' + 'sns.kdeplot(subssubub_data["' + str(self.x_var) + '"], subsubsub_data["' + str(self.y_var) + '"], ax = ax, shade = True, cbar = True, cmap = "cmo." + "'+str(cmap)+'" ) ' + '</p>'
                                        # ----------------------------
                                elif self.PLOT_TYPE == HISTGRAM:
                                    self.ax1.hist(data3[self.x_var], bins=bins_num, alpha=alpha, weights=np.zeros_like(data3[self.x_var])+1./data3[self.x_var].siz,label = pd.unique(self.csv[self.subsubcolor_var])[value3])
                                    # Log #-----------------------
                                    File_log_str += '<p>' + 'ax.hist(subsubsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(subsubsub_data["'+str(self.x_var)+'"])+1./subsubsub_data["' + str(self.x_var) + '"].size ' + ')' + '</p>'
                                    # ----------------------------
                                elif self.PLOT_TYPE == LINE:
                                    self.ax1.plot(data3[self.x_var].replace([np.inf, -np.inf], np.nan), data3[self.y_var].replace([np.inf, -np.inf], np.nan), alpha = alpha, linewidth = marker_size, label = pd.unique(self.csv[self.subsubcolor_var])[value3])
                                    # Log #-----------------------
                                    File_log_str += '<p>' + 'ax.plot(subsubsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), subsubsub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), linewidth = '+str(marker_size)+', alpha ='+str(alpha) + ')' + '</p>'
                                    # ----------------------------
                                elif self.PLOT_TYPE == BOXPLOT:
                                    sns.boxplot(y=self.y_var,x=self.x_var,data=data3,ax=self.ax1)
                                    # Log #-----------------------
                                    File_log_str += '<p>' + 'ax = sns.boxplot( x = "'+str(self.x_var)+'", y = "'+str(self.y_var)+'", data=subsubsub_data.replace([np.inf, -np.inf], np.nan).dropna() )' + '</p>'
                                    # ----------------------------
        
        self.fig.canvas.draw_idle()
        self.ui.tab_pca.setCurrentIndex(2)
        # Log #-----------------------
        File_log_str += '<p>' + 'plt.<span style = color:\"red\">show</span>()' + '</p>'
        File_log_str += '</div>'
        # ----------------------------
        # File_log_str = re.sub('.([])(', '.<span style = color:\"deepskyblue\">\\1</span>( ', File_log_str)

        self.onStringChanged(File_log_str)

    def graphDraw_nonNumeric_Syntax(self):
        # Syntax Coloring Setting #--------------------------
        
        # Log #-----------------------
        File_log_str = '#- Import CSV as DataFrame ---------- ' + '\n'
        File_log_str += 'FILE_PATH = \'' + str(self.CSV_PATH) + '\'' + '\n'
        File_log_str += 'DATA = pd.read_csv(FILE_PATH)' + '\n'
        File_log_str += '#- Axes Setting ---------- ' + '\n'
        File_log_str += 'fig, ax = plt.subplots()' + '\n'
        # ----------------------------

        #- plot initial setting -------------------------------------
        SCATTER = 0
        DENSITY = 1
        HISTGRAM = 2
        LINE = 3
        BOXPLOT = 4

        ALL_SORT = 0

        colors=["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]
        # marker_list = [  "o", ",", "^", "v", "*", "<", ">", "1", ".", "2", "3","4", "8", "s", "p", "h", "H", "+", "x", "D","d", "|", "_", "None", None, "", "$x$","$\\alpha$", "$\\beta$", "$\\gamma$"]
        # marker_list = [  "o", ",", "^", "v", "*", "<", ">", "1","s", "p", "h", "H", "+", "x", "D","d", "|", "_", "None", None, "", "$x$","$\\alpha$", "$\\beta$", "$\\gamma$"".", "2", "3","4", "8"]
        marker_list = [ 'o', 'v', '^', '<', '>', '8', 's', 'p', '*', 'h', 'H', 'D', 'd', 'P', 'X' ]
        edge_color = 'black'
        edge_width = 0.0
        # Log #-----------------------
        # File_log_str += 'colors=["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' +'\n'
        # File_log_str += '[ "o", "v", "^", "<", ">", "8", "s", "p", "*", "h", "H", "D", "d", "P", "X" ]' +'\n'
        # File_log_str += 'edge_color = "black"' +'\n'
        # File_log_str += 'edge_width = 0.0' +'\n'
        # ----------------------------

        # cmap_list = ["winter","autumn","summer","spring","pink","Wistia"]
        cmap_list = list(matplotlib.cm.cmap_d.keys())
        cmap = self.ui.cmb_cmap.currentText()
        alpha = self.ui.dsb_alpha.value()
        bins_num = self.ui.spb_bins.value()
        hist_alpha = self.ui.dsb_alpha.value()
        clen = len( colors )
        mlen = len( marker_list )
        cmaplen = len( cmap_list )
        marker_size = self.ui.dsb_markerSize.value()
        self.fig.clf()
        self.ax1.clear()
        self.ax1 = self.fig.add_subplot(111)
        titleText = self.ui.text_title.text()
        if titleText != '':
            self.ax1.set_title(str(titleText))
            # Log #-----------------------
            File_log_str += 'ax.set_title( "' + str(titleText) + '")' + '\n'
            # ----------------------------
        self.ax1.set_xlabel( self.x_var )
        # Log #-----------------------
        File_log_str += 'ax.set_xlabel( "' + str(self.x_var) + '")' + '\n'
        # ----------------------------
        if self.PLOT_TYPE != HISTGRAM: 
            self.ax1.set_ylabel( self.y_var )
            # Log #-----------------------
            File_log_str += 'ax.set_ylabel( "' + str(self.y_var) + '" )' + '\n'
            # ----------------------------
        elif self.PLOT_TYPE == HISTGRAM:
            self.ax1.set_ylabel('Frequency')
            # Log #-----------------------
            File_log_str += 'ax.set_ylabel( "Frequency" )' + '\n'
            # ----------------------------

        # x axis setting
        if self.PLOT_TYPE != HISTGRAM and self.ui.cb_logx.isChecked(): # Hist
            self.ax1.set_xscale('log')
            # Log #-----------------------
            File_log_str += 'ax.set_xscale( \'log\' )' + '\n'
            # ----------------------------
        if self.x_var in self.NUMERIC_HEADER_LIST:
            xmax = 0
            if self.ui.dsb_xmax.value() < self.ui.dsb_xmin.value():
                xmax = self.ui.dsb_xmin.value()
            else:
                xmax = self.ui.dsb_xmax.value()
            self.ax1.set_xlim( self.ui.dsb_xmin.value() , xmax )
            # Log #-----------------------
            # File_log_str += '<p>' + 'ax.<span style=\"color:deepskyblue\">set_xlim</span>( min(DATA[\'' + str(self.x_var) + '\'].replace([np.inf, -np.inf], np.nan ).dropna() ) - abs( min(DATA[\'' + str(self.x_var) + '\'].replace([np.inf, -np.inf], np.nan ).dropna() )/10), max(DATA[\''+str(self.x_var)+'\'].replace([np.inf, -np.inf], np.nan).dropna()) + abs(max(DATA[\''+str(self.x_var)+'\'].replace([np.inf, -np.inf], np.nan).dropna())/10)  )' +'</p>'
            File_log_str += 'ax.set_xlim(min(DATA[\'' + str(self.x_var) + '\'].replace([np.inf, -np.inf], np.nan ).dropna() ) - abs( min(DATA[\'' + str(self.x_var) + '\'].replace([np.inf, -np.inf], np.nan ).dropna() )/10), max(DATA[\''+str(self.x_var)+'\'].replace([np.inf, -np.inf], np.nan).dropna()) + abs(max(DATA[\''+str(self.x_var)+'\'].replace([np.inf, -np.inf], np.nan).dropna())/10)  )' + '\n'
            # ----------------------------
        # y axis setting
        if self.PLOT_TYPE != HISTGRAM: # Hist
            if self.ui.cb_logy.isChecked():
                self.ax1.set_yscale('log')
                # Log #-----------------------
                File_log_str += 'ax.set_yscale( \'log\' )' + '\n'
                # ----------------------------
        if self.y_var in self.NUMERIC_HEADER_LIST and self.PLOT_TYPE != HISTGRAM:
            ymax = 0
            if self.ui.dsb_ymax.value() < self.ui.dsb_ymin.value():
                ymax = self.ui.dsb_ymin.value()
            else:
                ymax = self.ui.dsb_ymax.value()
            self.ax1.set_ylim( self.ui.dsb_ymin.value() , ymax )
            # Log #-----------------------
            File_log_str += 'ax.set_ylim( min(DATA[\''+str(self.y_var) + '\'].replace([np.inf, -np.inf], np.nan ).dropna() ) - abs( min(DATA[\'' + str(self.y_var) + '\'].replace([np.inf, -np.inf], np.nan ).dropna() )/10), max(DATA[\''+str(self.y_var)+'\'].replace([np.inf, -np.inf], np.nan).dropna()) + abs(max(DATA[\''+str(self.y_var)+'\'].replace([np.inf, -np.inf], np.nan).dropna())/10)  )' + '\n'
            # ----------------------------
        # DATA PLOT
        #========================================================
        File_log_str += '#- PLOT ------------------ ' + '\n'
        if self.color_var == "None_": # simple plot (scatter)
            if self.PLOT_TYPE == SCATTER:
                self.ax1.scatter(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan), self.csv[self.y_var].replace([np.inf, -np.inf], np.nan), s = marker_size, alpha = alpha,edgecolor=edge_color,linewidth=edge_width)
                # Log #-----------------------
                File_log_str += 'ax.scatter(DATA["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), DATA["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), s = '+str(marker_size)+', alpha ='+str(alpha)+',edgecolor="' + str(edge_color)+'",linewidth= ' + str(edge_width) +')' + '\n'
                # ----------------------------
            elif self.PLOT_TYPE == DENSITY: #density
                if len(self.csv) != 0:
                    sns.kdeplot( self.csv[self.x_var], self.csv[self.y_var], ax = self.ax1, shade=True, cbar = True, cmap = "cmo."+cmap  )
                    # Log #-----------------------
                    File_log_str +=  'sns.kdeplot(DATA["' + str(self.x_var) + '"], DATA["' + str(self.y_var) + '"], ax = ax, shade = True, cbar = True, cmap = "cmo." + "'+str(cmap)+'" ) ' + '\n'
                    # ----------------------------
            elif self.PLOT_TYPE == HISTGRAM: #Histgoram
                self.ax1.hist(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan).dropna(), bins = bins_num, alpha = alpha, weights = np.zeros_like(self.csv[self.x_var])+1./self.csv[self.x_var].size)
                # Log #-----------------------
                File_log_str +=  'ax.hist(DATA["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(DATA["'+str(self.x_var)+'"])+1./DATA["' + str(self.x_var) + '"].size ' + ')' + '\n'
                # ----------------------------
            elif self.PLOT_TYPE == LINE: # line
                self.ax1.plot(self.csv[self.x_var].replace([np.inf, -np.inf], np.nan), self.csv[self.y_var].replace([np.inf, -np.inf], np.nan), linewidth = marker_size, alpha = alpha, color = colors[0])
                # Log #-----------------------
                File_log_str +=  'ax.plot( DATA["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), DATA["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), linewidth = '+str(marker_size)+', alpha ='+str(alpha)+ ', color = "' + str(colors[0]) + '" )' + '\n'
                # ----------------------------
            elif self.PLOT_TYPE == BOXPLOT:
                data = self.csv.replace([np.inf, -np.inf], np.nan).dropna()
                sns.boxplot(y=self.y_var,x=self.x_var,data=data,ax=self.ax1)
                # print(type(self.ax1))
                # Log #-----------------------
                File_log_str +=  'ax = sns.boxplot( x = "'+str(self.x_var)+'", y = "'+str(self.y_var)+'", data=DATA.replace([np.inf, -np.inf], np.nan).dropna() )' + '\n'
                # ----------------------------
        else:
            isNumeric = True
            for comp in self.csv[self.color_var]:
                if isinstance(comp,str):
                    isNumeric = False
                    break
            if self.ui.cmb_sort.currentIndex() == ALL_SORT: # use discrete colors and plot all
                for i, value in enumerate(pd.unique(self.csv[self.color_var])):
                    color_index = i%clen
                    marker_index = i%mlen
                    cmap_index = i%cmaplen
                    data = self.csv.loc[ self.csv[self.color_var] == value ]
                    # scatter graph
                    if self.PLOT_TYPE == SCATTER: # scatter
                        self.ax1.scatter(data[self.x_var].replace([np.inf, -np.inf], np.nan), data[self.y_var].replace([np.inf, -np.inf], np.nan) , color = colors[color_index], marker = marker_list[marker_index], alpha = alpha, s = marker_size, label = value)
                    elif self.PLOT_TYPE == DENSITY: # density 
                        if len(data) != 0:
                            temp_clr = [colors[color_index],colors[color_index],colors[color_index]]
                            values = range(len(temp_clr))
                            vmax = np.ceil(np.max(values))
                            clr_list = []
                            for v, c in zip(values, temp_clr):
                                clr_list.append( ( v/ vmax, c) )
                            cmap = LinearSegmentedColormap.from_list('custom_cmap', clr_list)
                            sns.kdeplot( data[self.x_var].replace([np.inf, -np.inf], np.nan), data[self.y_var].replace([np.inf, -np.inf], np.nan),shade=False, ax = self.ax1, cmap = cmap )
                            # cset = kde2dgraph(self.ax1, data[self.x_var], data[self.y_var], min(self.csv[self.x_var]),max(self.csv[self.x_var]),min(self.csv[self.y_var]),max(self.csv[self.y_var]),cmap_list[cmap_index])
                    elif self.PLOT_TYPE == HISTGRAM: # Histogram
                        self.ax1.hist(data[self.x_var], bins = bins_num, alpha = hist_alpha, weights = np.zeros_like(data[self.x_var])+1./data[self.x_var].size,label = value)
                    elif self.PLOT_TYPE == LINE:
                        self.ax1.plot(data[self.x_var].replace([np.inf, -np.inf], np.nan), data[self.y_var].replace([np.inf, -np.inf], np.nan) , color = colors[color_index], alpha = alpha, linewidth = marker_size, label = value)
                if self.PLOT_TYPE == BOXPLOT:
                    data = self.csv.replace([np.inf, -np.inf], np.nan).dropna()
                    sns.boxplot(y=self.y_var, x=self.x_var, hue = self.color_var, data=data, ax=self.ax1)
                # Log #-----------------------
                # File_log_str += '<span style=\" font-size:13pt; font-weight:600; color:#7F7F7F;\" >'
                # File_log_str += '#- Lists of Colors and Markers ---------- ' + '\n'
                # File_log_str += '</span>'
                
                if self.PLOT_TYPE == BOXPLOT:
                    File_log_str +=   'sns.boxplot( x = "' + str(self.x_var) + '", y = "' + str(self.y_var) + '", hue = "' + str(self.color_var) + '", data = DATA.replace([np.inf, -np.inf], np.nan).dropna(), ax = ax )' + '\n'
                else:
                    File_log_str +=   'for i, value in enumerate( pd.unique( DATA["' + str(self.color_var) + '"] ) ):' + '\n'
                    File_log_str +=   '    ' + 'sub_data = DATA.loc[ DATA["' + str(self.color_var) + '"] == value ]' + '\n'
                    if self.PLOT_TYPE == SCATTER:
                        File_log_str +=   '    ' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '\n'
                        File_log_str +=   '    ' + 'markers = [ "o", "v", "^", "<", ">", "8", "s", "p", "*", "h", "H", "D", "d", "P", "X" ]' + '\n'
                        File_log_str +=   '    ' + 'c_index = i%len(colors)' + '\n'
                        File_log_str +=   '    ' + 'm_index = i%len(markers)' + '\n'
                        File_log_str +=   '    ' + 'ax.scatter( sub_data["'+ str(self.x_var) +'"].replace([np.inf, -np.inf], np.nan), sub_data["'+ str(self.y_var) +'"].replace([np.inf, -np.inf], np.nan), color = colors[c_index], marker = markers[m_index], alpha = '+str(alpha)+', s = '+str(marker_size)+', label = value)' + '\n'
                    elif self.PLOT_TYPE == DENSITY:
                        # File_log_str +=    '    '+'cm_index = i%len(cmaps)'  
                        File_log_str +=   '    ' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '\n'
                        File_log_str +=   '    ' + 'c_index = i%len(colors)' + '\n'
                        File_log_str +=   '    ' + 'sns.kdeplot(sub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), sub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), shade = False, ax = ax, cmap = generate_cmap([colors[c_index],colors[c_index],colors[c_index]]) )' + '\n'
                    elif self.PLOT_TYPE == HISTGRAM:
                        File_log_str +=   '    ' + 'ax.hist(sub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(sub_data["'+str(self.x_var)+'"])+1./sub_data["' + str(self.x_var) + '"].size ' + ')' + '\n'
                    elif self.PLOT_TYPE == LINE:
                        File_log_str +=   '    ' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '\n'
                        File_log_str +=   '    ' + 'c_index = i%len(colors)' + '\n'
                        File_log_str +=   '    ' + 'ax.plot( sub_data["'+ str(self.x_var) +'"].replace([np.inf, -np.inf], np.nan), sub_data["'+ str(self.y_var) +'"].replace([np.inf, -np.inf], np.nan), color = colors[c_index], alpha = '+str(alpha)+', linewidth = '+str(marker_size)+', label = value )' + '\n'
                # ----------------------------
            else:  # Sorting by specific value
                value = self.ui.cmb_sort.currentIndex() - 1
                data = self.csv.loc[ self.csv[self.color_var] == pd.unique(self.csv[self.color_var])[value] ]
                # Log #-----------------------
                File_log_str +=  'sub_data = DATA.loc[ DATA["' + str(self.color_var) + '"] == "'+str(pd.unique(self.csv[self.color_var])[value])+'"]' + '\n'
                # ----------------------------
                if self.subcolor_var == 'None_': 
                    # scatter graph
                    if self.PLOT_TYPE == SCATTER:
                        self.ax1.scatter(data[self.x_var].replace([np.inf, -np.inf], np.nan), data[self.y_var].replace([np.inf, -np.inf], np.nan), alpha = alpha, s = marker_size, label = pd.unique(self.csv[self.color_var])[value])
                        # Log #-----------------------
                        File_log_str +=  'ax.scatter(sub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), sub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), s = '+str(marker_size)+', alpha ='+str(alpha)+',edgecolor="' + str(edge_color)+'",linewidth= ' + str(edge_width) +')' + '\n'
                        # ----------------------------
                    elif self.PLOT_TYPE == DENSITY: # Density plot (when x and y are the same, it stacks)
                        if len(data) != 2:
                            sns.kdeplot(self.ax1,data[self.x_var].replace([np.inf, -np.inf], np.nan),data[self.y_var].replace([np.inf, -np.inf], np.nan), shade=True, cbar = True, cmap = "cmo."+cmap )
                            # Log #-----------------------
                            File_log_str +=  'sns.kdeplot(sub_data["' + str(self.x_var) + '"], sub_data["' + str(self.y_var) + '"], ax = ax, shade = True, cbar = True, cmap = "cmo." + "'+str(cmap)+'" ) ' + '\n'
                            # ----------------------------
                    elif self.PLOT_TYPE == HISTGRAM:
                        self.ax1.hist(data[self.x_var], bins = bins_num, alpha = alpha, weights=np.zeros_like(data[self.x_var])+1./data[self.x_var].size,label = pd.unique(self.csv[self.color_var])[value])
                        # Log #-----------------------
                        File_log_str +=  'ax.hist(sub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(sub_data["'+str(self.x_var)+'"])+1./sub_data["' + str(self.x_var) + '"].size ' + ')' + '\n'
                        # ----------------------------
                    elif self.PLOT_TYPE == LINE:
                        self.ax1.plot(data[self.x_var].replace([np.inf, -np.inf], np.nan), data[self.y_var].replace([np.inf, -np.inf], np.nan), alpha = alpha, linewidth = marker_size, label = pd.unique(self.csv[self.color_var])[value])
                        # Log #-----------------------
                        File_log_str +=  'ax.plot(sub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), sub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), linewidth = '+str(marker_size)+', alpha ='+str(alpha) + ')' + '\n'
                        # ----------------------------
                    elif self.PLOT_TYPE == BOXPLOT:
                        sns.boxplot(y=self.y_var,x=self.x_var,data=data,ax=self.ax1)
                        # Log #-----------------------
                        File_log_str +=  'ax = sns.boxplot( x = "'+str(self.x_var)+'", y = "'+str(self.y_var)+'", data=sub_data.replace([np.inf, -np.inf], np.nan).dropna() )' + '\n'
                        # ----------------------------

                else:
                    if self.ui.cmb_subsort.currentIndex() == ALL_SORT: # use discrete colors and plot all
                        for i, value2 in enumerate(pd.unique(data[self.subcolor_var])):
                            color_index = i%clen
                            marker_index = i%mlen
                            cmap_index = i%cmaplen
                            data2 = data.loc[ data[self.subcolor_var] == value2 ]
                            # scatter graph
                            if self.PLOT_TYPE == SCATTER: 
                                self.ax1.scatter(data2[self.x_var].replace([np.inf, -np.inf], np.nan), data2[self.y_var].replace([np.inf, -np.inf], np.nan), color = colors[color_index], marker = marker_list[marker_index], alpha = alpha, s = marker_size, label = value2)
                            elif self.PLOT_TYPE == DENSITY: 
                                if len(data2) != 0:
                                    temp_clr = [colors[color_index],colors[color_index],colors[color_index]]
                                    values = range(len(temp_clr))
                                    vmax = np.ceil(np.max(values))
                                    clr_list = []
                                    for v, c in zip(values, temp_clr):
                                        clr_list.append( ( v/ vmax, c) )
                                    cmap = LinearSegmentedColormap.from_list('custom_cmap', clr_list)
                                    sns.kdeplot( data2[self.x_var].replace([np.inf, -np.inf], np.nan), data2[self.y_var].replace([np.inf, -np.inf], np.nan),shade=False, ax = self.ax1, cmap = cmap )
                                    # cset = kde2dgraph(self.ax1, data2[self.x_var], data2[self.y_var], min(self.csv[self.x_var]),max(self.csv[self.x_var]),min(self.csv[self.y_var]),max(self.csv[self.y_var]),cmap_list[cmap_index])
                            elif self.PLOT_TYPE == HISTGRAM:
                                self.ax1.hist(data2[self.x_var], bins=bins_num, alpha=hist_alpha, weights=np.zeros_like(data2[self.x_var])+1./data2[self.x_var].size, label = value2)
                            elif self.PLOT_TYPE == LINE:
                                self.ax1.plot(data2[self.x_var].replace([np.inf, -np.inf], np.nan), data2[self.y_var].replace([np.inf, -np.inf], np.nan), color = colors[color_index], alpha = alpha, linewidth = marker_size, label = value2)
                        if self.PLOT_TYPE == BOXPLOT:
                            sns.boxplot(y=self.y_var, x=self.x_var, hue = self.subcolor_var, data=data.replace([np.inf, -np.inf], np.nan).dropna(), ax=self.ax1)

                        # Log #-----------------------
                        # File_log_str += '<span style=\" font-size:13pt; font-weight:600; color:#7F7F7F;\" >'
                        # File_log_str += '#- Lists of Colors and Markers ---------- ' + '\n'
                        # File_log_str += '</span>'
                        # if self.PLOT_TYPE != DENSITY:
                        #     File_log_str +=   'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]'  
                        #     File_log_str +=   'markers = [ "o", "v", "^", "<", ">", "8", "s", "p", "*", "h", "H", "D", "d", "P", "X" ]'  
                        # else:
                        #     File_log_str +=   'cmaps = list(matplotlib.cm.cmap_d.keys())'  
                        if self.PLOT_TYPE == BOXPLOT:
                            File_log_str +=   'sns.boxplot( x = "' + str(self.x_var) + '", y = "' + str(self.y_var) + '", hue = "' + str(self.subcolor_var) + '", data = sub_data.replace([np.inf, -np.inf], np.nan).dropna(), ax = ax )' + '\n'  
                        else:
                            File_log_str +=   'for i, value in enumerate( pd.unique( sub_data["' + str(self.subcolor_var) + '"] ) ):' + '\n'
                            File_log_str +=   '    ' + 'subsub_data = sub_data.loc[ sub_data["' + str(self.subcolor_var) + '"] == value ]' + '\n'
                            if self.PLOT_TYPE == SCATTER:
                                File_log_str +=   '    ' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '\n'
                                File_log_str +=   '    ' + 'markers = [ "o", "v", "^", "<", ">", "8", "s", "p", "*", "h", "H", "D", "d", "P", "X" ]' + '\n'
                                File_log_str +=   '    ' + 'c_index = i%len(colors)' + '\n'
                                File_log_str +=   '    ' + 'm_index = i%len(markers)' + '\n'
                                File_log_str +=   '    ' + 'ax.scatter( subsub_data["'+ str(self.x_var) +'"].replace([np.inf, -np.inf], np.nan), subsub_data["'+ str(self.y_var) +'"].replace([np.inf, -np.inf], np.nan), color = colors[c_index], marker = markers[m_index], alpha = '+str(alpha)+', s = '+str(marker_size)+', label = value) )' + '\n'
                            elif self.PLOT_TYPE == DENSITY:
                                File_log_str +=   '    ' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '\n'
                                File_log_str +=   '    ' + 'c_index = i%len(colors)' + '\n'
                                File_log_str +=   '    ' + 'sns.kdeplot( subsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), subsub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), shade = False, ax = ax, cmap = generate_cmap([colors[c_index],colors[c_index],colors[c_index]]) )' + '\n'
                                # File_log_str +=    '    '+'cset = kde2dgraph(ax, subsub_data["'+str(self.x_var)+'"], subsub_data["'+str(self.y_var)+'"], min(DATA["'+str(self.x_var)+'"]), max(DATA["'+str(self.x_var)+'"]),min(DATA["'+str(self.y_var)+'"]),max(DATA["'+str(self.y_var)+'"]),cmaps[cm_index])'  
                            elif self.PLOT_TYPE == HISTGRAM:
                                # File_log_str +=    '    '+'c_index = i%len(colors)'  
                                File_log_str +=   '    ' + 'ax.hist(subsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(subsub_data["'+str(self.x_var)+'"])+1./subsub_data["' + str(self.x_var) + '"].size ' + ')' + '\n'
                            elif self.PLOT_TYPE == LINE:
                                File_log_str +=   '    ' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '\n'
                                File_log_str +=   '    ' + 'c_index = i%len(colors)' + '\n'
                                File_log_str +=   '    ' + 'ax.plot( subsub_data["'+ str(self.x_var) +'"].replace([np.inf, -np.inf], np.nan), subsub_data["'+ str(self.y_var) +'"].replace([np.inf, -np.inf], np.nan), color = colors[c_index], alpha = '+str(alpha)+', linewidth = '+str(marker_size)+', label = value )' + '\n'
                        # ----------------------------
                    else:
                        value2 = self.ui.cmb_subsort.currentIndex() - 1
                        data2 = data.loc[ data[ self.subcolor_var ] == pd.unique(self.csv[self.subcolor_var])[value2] ]
                        # Log #-----------------------
                        File_log_str +=  'subsub_data = sub_data.loc[ sub_data["' + str(self.subcolor_var) + '"] == "'+str(pd.unique(self.csv[self.subcolor_var])[value2])+'"]' + '\n'
                        # ----------------------------
                        if self.subsubcolor_var == 'None_':
                            if self.PLOT_TYPE == SCATTER:
                                self.ax1.scatter(data2[self.x_var].replace([np.inf, -np.inf], np.nan), data2[self.y_var].replace([np.inf, -np.inf], np.nan), alpha = alpha, s = marker_size, label = pd.unique(self.csv[self.subcolor_var])[value2])
                                # Log #-----------------------
                                File_log_str +=  'ax.scatter(subsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), subsub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), s = '+str(marker_size)+', alpha ='+str(alpha)+',edgecolor="' + str(edge_color)+'",linewidth= ' + str(edge_width) +')' + '\n'
                                # ----------------------------
                            elif self.PLOT_TYPE == DENSITY: # Density plot (when x and y are the same, it stacks)
                                if len(data2) != 0:
                                    sns.kdeplot(self.ax1,data2[self.x_var].replace([np.inf, -np.inf], np.nan),data2[self.y_var].replace([np.inf, -np.inf], np.nan), shade=True, cbar = True, cmap = "cmo."+cmap )
                                    # Log #-----------------------
                                    File_log_str +=  'sns.kdeplot(subsub_data["' + str(self.x_var) + '"], subsub_data["' + str(self.y_var) + '"], ax = ax, shade = True, cbar = True, cmap = "cmo." + "'+str(cmap)+'" ) ' + '\n'
                                    # ----------------------------
                                    # cfset = kde2dgraphfill(self.ax1,data2[self.x_var],data2[self.y_var],min(self.csv[self.x_var]),max(self.csv[self.x_var]),min(self.csv[self.y_var]),max(self.csv[self.y_var]))
                                    # cax = self.fig.add_axes([0.8, 0.2, 0.05, 0.5])
                                    # self.fig.colorbar(cfset,cax=cax,orientation='vertical')
                            elif self.PLOT_TYPE == HISTGRAM:
                                self.ax1.hist(data2[self.x_var], bins=bins_num, alpha=alpha, weights=np.zeros_like(data2[self.x_var])+1./data2[self.x_var].size, label = pd.unique(self.csv[self.subcolor_var])[value2])
                                # Log #-----------------------
                                File_log_str +=  'ax.hist(subsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(subsub_data["'+str(self.x_var)+'"])+1./subsub_data["' + str(self.x_var) + '"].size ' + ')' + '\n'
                                # ----------------------------
                            elif self.PLOT_TYPE == LINE:
                                self.ax1.plot(data2[self.x_var].replace([np.inf, -np.inf], np.nan), data2[self.y_var].replace([np.inf, -np.inf], np.nan), alpha = alpha, linewidth = marker_size, label = pd.unique(self.csv[self.subcolor_var])[value2])
                                # Log #-----------------------
                                File_log_str +=  'ax.plot(subsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), subsub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), linewidth = '+str(marker_size)+', alpha ='+str(alpha) + ')' + '\n'
                                # ----------------------------
                            elif self.PLOT_TYPE == BOXPLOT:
                                sns.boxplot(y=self.y_var,x=self.x_var,data=data2,ax=self.ax1)
                                # Log #-----------------------
                                File_log_str +=  'ax = sns.boxplot( x = "'+str(self.x_var)+'", y = "'+str(self.y_var)+'", data=subsub_data.replace([np.inf, -np.inf], np.nan).dropna() )' + '\n'
                                # ----------------------------
                        else:
                            if self.ui.cmb_subsubsort.currentIndex() == ALL_SORT: # use discrete colors and plot all
                                for i, value3 in enumerate(pd.unique(self.csv[self.subsubcolor_var])):
                                    color_index = i%clen
                                    marker_index = i%mlen
                                    cmap_index = i%cmaplen
                                    data3 = data2.loc[ data2[self.subsubcolor_var] == value3 ]
                                    # scatter graph
                                    if self.PLOT_TYPE == SCATTER: 
                                        self.ax1.scatter(data3[self.x_var].replace([np.inf, -np.inf], np.nan), data3[self.y_var].replace([np.inf, -np.inf], np.nan), color = colors[color_index], marker = marker_list[marker_index], alpha = alpha, s = marker_size, label = value3)
                                    elif self.PLOT_TYPE == DENSITY: 
                                        if len(data3) != 0:
                                            temp_clr = [colors[color_index],colors[color_index],colors[color_index]]
                                            values = range(len(temp_clr))
                                            vmax = np.ceil(np.max(values))
                                            clr_list = []
                                            for v, c in zip(values, temp_clr):
                                                clr_list.append( ( v/ vmax, c) )
                                            cmap = LinearSegmentedColormap.from_list('custom_cmap', clr_list)
                                            sns.kdeplot( data3[self.x_var].replace([np.inf, -np.inf], np.nan), data3[self.y_var].replace([np.inf, -np.inf], np.nan),shade=False, ax = self.ax1, cmap = cmap )
                                            # cset = kde2dgraph(self.ax1, data3[self.x_var], data3[self.y_var], min(self.csv[self.x_var]),max(self.csv[self.x_var]),min(self.csv[self.y_var]),max(self.csv[self.y_var]),cmap_list[cmap_index]) 
                                    elif self.PLOT_TYPE == HISTGRAM:
                                        self.ax1.hist(data3[self.x_var], bins=bins_num, alpha=hist_alpha, weights=np.zeros_like(data3[self.x_var])+1./data3[self.x_var].size, label = value3)
                                    elif self.PLOT_TYPE == LINE:
                                        self.ax1.plot(data3[self.x_var].replace([np.inf, -np.inf], np.nan), data3[self.y_var].replace([np.inf, -np.inf], np.nan), color = colors[color_index], alpha = alpha, linewidth = marker_size, label = value3)
                                if self.PLOT_TYPE == BOXPLOT:
                                    sns.boxplot(y=self.y_var, x=self.x_var, hue = self.subsubcolor_var, data=data2.replace([np.inf, -np.inf], np.nan).dropna(), ax=self.ax1)

                                # Log #-----------------------
                                # File_log_str += '<span style=\" font-size:13pt; font-weight:600; color:#7F7F7F;\" >'
                                # File_log_str += '#- Lists of Colors and Markers ---------- ' + '\n'
                                # File_log_str += '</span>'
                                # if self.PLOT_TYPE != DENSITY:
                                #     File_log_str +=   'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]'  
                                #     File_log_str +=   'markers = [ "o", "v", "^", "<", ">", "8", "s", "p", "*", "h", "H", "D", "d", "P", "X" ]'  
                                # else:
                                #     File_log_str +=   'cmaps = list(matplotlib.cm.cmap_d.keys())'  
                                if self.PLOT_TYPE == BOXPLOT:
                                    File_log_str +=  'sns.boxplot( x = "' + str(self.x_var) + '", y = "' + str(self.y_var) + '", hue = "' + str(self.subsubcolor_var) + '", data = subsub_data.replace([np.inf, -np.inf], np.nan).dropna(), ax = ax )' + '\n'
                                else:
                                    File_log_str +=  'for i, value in enumerate( pd.unique( subsub_data["' + str(self.subsubcolor_var) + '"] ) ):' + '\n'
                                    File_log_str +=   '    ' + 'subsubsub_data = subsub_data.loc[ subsub_data["' + str(self.subsubcolor_var) + '"] == value ]' + '\n'
                                    if self.PLOT_TYPE == SCATTER:
                                        File_log_str +=  '    ' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '\n'
                                        File_log_str +=  '    ' + 'markers = [ "o", "v", "^", "<", ">", "8", "s", "p", "*", "h", "H", "D", "d", "P", "X" ]' + '\n'
                                        File_log_str +=  '    ' + 'c_index = i%len(colors)' + '\n'
                                        File_log_str +=  '    ' + 'm_index = i%len(markers)' + '\n'
                                        File_log_str +=  '    ' + 'ax.scatter( subsubsub_data["'+ str(self.x_var) +'"].replace([np.inf, -np.inf], np.nan), subsubsub_data["'+ str(self.y_var) +'"].replace([np.inf, -np.inf], np.nan), color = colors[c_index], marker = markers[m_index], alpha = '+str(alpha)+', s = '+str(marker_size)+', label = value) )' + '\n'
                                    elif self.PLOT_TYPE == DENSITY:
                                        # File_log_str +=   '    '+'cm_index = i%len(cmaps)'  
                                        File_log_str +=  '    ' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '\n'
                                        File_log_str +=  '    ' + 'c_index = i%len(colors)' + '\n'
                                        File_log_str +=  '    ' + 'sns.kdeplot( subsubsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), subsubsub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), shade = False, ax = ax, cmap = generate_cmap([colors[c_index],colors[c_index],colors[c_index]]) )' + '\n'
                                        # File_log_str +=   '    '+'cset = kde2dgraph(ax, subsubsub_data["'+str(self.x_var)+'"], subsubsub_data["'+str(self.y_var)+'"], min(DATA["'+str(self.x_var)+'"]), max(DATA["'+str(self.x_var)+'"]),min(DATA["'+str(self.y_var)+'"]),max(DATA["'+str(self.y_var)+'"]),cmaps[cm_index])'  
                                    elif self.PLOT_TYPE == HISTGRAM:
                                        # File_log_str +=   'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]'  
                                        # File_log_str +=   '    '+'c_index = i%len(colors)'  
                                        File_log_str +=  '    ' + 'ax.hist(subsubsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(subsubsub_data["'+str(self.x_var)+'"])+1./subsubsub_data["' + str(self.x_var) + '"].size ' + ')' + '\n'
                                    elif self.PLOT_TYPE == LINE:
                                        File_log_str +=  '    ' + 'colors = ["#005AFF", "#FF4B00","#03AF7A", "#804000", "#990099", "#FF8082", "#4DC4FF", "#F6AA00"]' + '\n'
                                        File_log_str +=  '    ' + 'c_index = i%len(colors)' + '\n'
                                        File_log_str +=  '    ' + 'ax.plot( subsubsub_data["'+ str(self.x_var) +'"].replace([np.inf, -np.inf], np.nan), subsubsub_data["'+ str(self.y_var) +'"].replace([np.inf, -np.inf], np.nan), color = colors[c_index], alpha = '+str(alpha)+', linewidth = '+str(marker_size)+', label = value )' + '\n'
                                # ----------------------------    
                            else:
                                value3 = self.ui.cmb_subsubsort.currentIndex() - 1
                                data3 = data2.loc[ data2[ self.subsubcolor_var ] == pd.unique(self.csv[self.subsubcolor_var])[value3] ]
                                # Log #-----------------------
                                File_log_str +=  'subsubsub_data = subsub_data.loc[ subsub_data["' + str(self.subsubcolor_var) + '"] == "'+str(pd.unique(self.csv[self.subsubcolor_var])[value3])+'"]'  
                                # ----------------------------
                                # scatter graph
                                if self.PLOT_TYPE == SCATTER:
                                    self.ax1.scatter(data3[self.x_var].replace([np.inf, -np.inf], np.nan), data3[self.y_var].replace([np.inf, -np.inf], np.nan), alpha = alpha, s = marker_size, label = pd.unique(self.csv[self.subsubcolor_var])[value3])
                                    # Log #-----------------------
                                    File_log_str +=  'ax.scatter(subsubsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), subsubsub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), s = '+str(marker_size)+', alpha ='+str(alpha)+',edgecolor="' + str(edge_color)+'",linewidth= ' + str(edge_width) +')' + '\n'
                                    # ----------------------------
                                elif self.PLOT_TYPE == DENSITY: # Density plot (when x and y are the same, it stacks)
                                    if len(data3) != 0:
                                        sns.kdeplot(self.ax1,data3[self.x_var].replace([np.inf, -np.inf], np.nan),data3[self.y_var].replace([np.inf, -np.inf], np.nan), shade=True, cbar = True, cmap = "cmo."+cmap )
                                        # Log #-----------------------
                                        File_log_str +=  'sns.kdeplot(subssubub_data["' + str(self.x_var) + '"], subsubsub_data["' + str(self.y_var) + '"], ax = ax, shade = True, cbar = True, cmap = "cmo." + "'+str(cmap)+'" ) ' + '\n'
                                        # ----------------------------
                                elif self.PLOT_TYPE == HISTGRAM:
                                    self.ax1.hist(data3[self.x_var], bins=bins_num, alpha=alpha, weights=np.zeros_like(data3[self.x_var])+1./data3[self.x_var].siz,label = pd.unique(self.csv[self.subsubcolor_var])[value3])
                                    # Log #-----------------------
                                    File_log_str +=  'ax.hist(subsubsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan).dropna(), bins = ' + str(bins_num) + ', alpha ='+str(alpha)+', weights = np.zeros_like(subsubsub_data["'+str(self.x_var)+'"])+1./subsubsub_data["' + str(self.x_var) + '"].size ' + ')' + '\n'
                                    # ----------------------------
                                elif self.PLOT_TYPE == LINE:
                                    self.ax1.plot(data3[self.x_var].replace([np.inf, -np.inf], np.nan), data3[self.y_var].replace([np.inf, -np.inf], np.nan), alpha = alpha, linewidth = marker_size, label = pd.unique(self.csv[self.subsubcolor_var])[value3])
                                    # Log #-----------------------
                                    File_log_str +=  'ax.plot(subsubsub_data["'+str(self.x_var)+'"].replace([np.inf, -np.inf], np.nan), subsubsub_data["'+str(self.y_var)+'"].replace([np.inf, -np.inf], np.nan), linewidth = '+str(marker_size)+', alpha ='+str(alpha) + ')' + '\n'
                                    # ----------------------------
                                elif self.PLOT_TYPE == BOXPLOT:
                                    sns.boxplot(y=self.y_var,x=self.x_var,data=data3,ax=self.ax1)
                                    # Log #-----------------------
                                    File_log_str +=  'ax = sns.boxplot( x = "'+str(self.x_var)+'", y = "'+str(self.y_var)+'", data=subsubsub_data.replace([np.inf, -np.inf], np.nan).dropna() )' + '\n'
                                    # ----------------------------
        self.ax1.legend()
        if self.ui.cb_legend.isChecked():
            self.ax1.legend().set_visible(True)
        else:
            self.ax1.legend().set_visible(False)
        self.fig.canvas.draw_idle()
        self.ui.tab_pca.setCurrentIndex(2)
        # Log #-----------------------
        File_log_str +=  'plt.show()' + '\n'
        # ----------------------------
        # File_log_str = re.sub('.([])(', '.<span style = color:\"deepskyblue\">\\1</span>( ', File_log_str)

        self.onStringChanged(File_log_str)

    def saveFigure(self):
        file_name, _ = Qw.QFileDialog.getSaveFileName(self)
        if len(file_name)==0:
            return
        file_name = str(Path(file_name).with_suffix(".pdf"))
        self.fig.savefig(file_name,bbox_inches='tight')


def generate_cmap(colors):
    """Return original color maps"""
    values = range(len(colors))
    vmax = np.ceil(np.max(values))
    color_list = []
    for v, c in zip(values, colors):
        color_list.append( ( v/ vmax, c) )
    return LinearSegmentedColormap.from_list('custom_cmap', color_list)

def kde2dgraphfill(ax,x,y,xmin,xmax,ymin,ymax):
    # Peform the kernel density estimate
    xx, yy = np.mgrid[xmin:xmax:100j, ymin:ymax:100j]
    positions = np.vstack([xx.ravel(), yy.ravel()])
    values = np.vstack([x, y])
    noise_param = 1.0
    try:
        kernel = st.gaussian_kde(values)
    except np.linalg.linalg.LinAlgError:
        row = len(x)
        mean_x = np.mean(x)
        mean_y = np.mean(y)
        dev_x = np.std(x)
        dev_y = np.std(y)
        noise_param = mean_y + mean_x + dev_y + dev_x
        if noise_param == 0:
            noise_param = 1
        elif noise_param > 1:
            # noise_param = 1.0 / noise_param
            noise_param = noise_param / 2
        elif noise_param < 0:
            noise_param = -1*noise_param
        else:
            noise_param = noise_param
        ####################
        # CHECK HERE !!!!!!!
        ####################
        rd_array = np.random.rand(row) * noise_param * 1/1000
        x_dash = x + rd_array
        values = np.vstack([x_dash, y])
        kernel = st.gaussian_kde(values)
    # kernel = st.gaussian_kde(values)
    f = np.reshape(kernel(positions).T, xx.shape)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    # cm = generate_cmap(['aqua', 'lawngreen', 'yellow', 'coral'])
    # cm = generate_cmap(['ghostwhite', 'deepskyblue', 'mediumblue', 'darkblue'])
    cfset = ax.contourf(xx, yy, f, cmap=plt.cm.jet)
    cfset = ax.contourf(xx, yy, f, cmap="jet")
    # cfset = ax.contourf(xx, yy, f, cmap=cm)
    cset = ax.contour(xx, yy, f, colors='k')
    return cfset
    
def kde2dgraph(ax,x,y,xmin,xmax,ymin,ymax,cmap):
    # Peform the kernel density estimate
    xx, yy = np.mgrid[xmin:xmax:100j, ymin:ymax:100j]
    positions = np.vstack([xx.ravel(), yy.ravel()])
    values = np.vstack([x, y])
    noise_param = 1.0
    try:
        kernel = st.gaussian_kde(values)
    except np.linalg.linalg.LinAlgError:
        row = len(x)
        mean_x = np.mean(x)
        mean_y = np.mean(y)
        dev_x = np.std(x)
        dev_y = np.std(y)
        noise_param = mean_y + mean_x + dev_y + dev_x
        if noise_param == 0:
            noise_param = 1
        elif noise_param > 1:
            # noise_param = 1.0 / noise_param
            noise_param = noise_param / 2
        elif noise_param < 0:
            noise_param = -1*noise_param
        else:
            noise_param = noise_param
        rd_array = np.random.rand(row) * noise_param * 1/1000
        x_dash = x + rd_array
        values = np.vstack([x_dash, y])
        kernel = st.gaussian_kde(values) 
    # except ValueError:
        # return "valueError"

    # kernel = st.gaussian_kde(values)
    f = np.reshape(kernel(positions).T, xx.shape)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    # cfset = ax.contourf(xx, yy, f, cmap=cmap)
    cset = ax.contour(xx, yy, f, cmap=cmap)
    return cset

# if __name__ == '__main__':
def buildGUI(data = 'None'):
    app = Qw.QApplication(sys.argv)         
    wmain = Csviwer()
    wmain.show()
    if type(data) == pd.core.frame.DataFrame:
        wmain.loadData(data)
    sys.exit(app.exec_())
        