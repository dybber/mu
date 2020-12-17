from PyQt5.QtCore import (
    Qt,
    pyqtSignal,
    QDir,
    QSortFilterProxyModel,
    QAbstractListModel,
)
from PyQt5.QtWidgets import (
    QFileSystemModel,
    QFileIconProvider,
)


class SortedFileSystem(QSortFilterProxyModel):
    """
    Sorted file system model, with ".." dir placed first, the "." dir
    not displayed then other directories and then files (similar to
    Total Commander)
    """

    delete = pyqtSignal(str)

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.setSourceModel(model)
        self.sourceModel().dataChanged.connect(self.invalidate)
        self.sort(0)
        self.delete.connect(self.sourceModel().do_delete)

    def lessThan(self, left, right):
        """
        Sort file list with .. first, then directories, then files
        """
        # https://stackoverflow.com/questions/10789284/
        source_model = self.sourceModel()
        left_name = source_model.data(left, Qt.DisplayRole)
        right_name = source_model.data(right, Qt.DisplayRole)
        if left_name == "..":
            return True
        if right_name == "..":
            return False

        left_is_dir = source_model.is_directory(left)
        right_is_dir = source_model.is_directory(right)
        if not left_is_dir and right_is_dir:
            return False
        if left_is_dir and not right_is_dir:
            return True

        return super().lessThan(left, right)

    def is_directory(self, index):
        """
        Is the given index refering to a directory?
        """
        ix = self.mapToSource(index)
        return self.sourceModel().is_directory(ix)

    def get_root_index(self):
        """
        What is the root index of this model?
        """
        indexRoot = self.sourceModel().get_root_index()
        return self.mapFromSource(indexRoot)

    def enter_directory(self, index):
        """
        Move into the given directory
        """
        ix = self.mapToSource(index)
        indexRoot = self.sourceModel().enter_directory(ix)
        return self.mapFromSource(indexRoot)


class LocalFileSystem(QFileSystemModel):

    delete = pyqtSignal(str)
    
    def __init__(self, home, parent=None):
        super().__init__(parent)
        self.home = home
        self.setRootPath(home)
        self.setFilter(QDir.AllDirs | QDir.AllEntries | QDir.NoDot)

    def is_directory(self, index):
        return self.isDir(index)

    def get_root_index(self):
        return self.index(self.rootPath())

    def enter_directory(self, index):
        sourcePath = self.fileInfo(index).absoluteFilePath()
        return self.index(sourcePath)

    def do_delete(self, filename):
        pass

    def rmdir(self, name):
        pass

    def move(self, name, new_name):
        """
        Move or rename a file
        """
        pass


class DeviceFileSystem(QAbstractListModel):
    """
    This is file system model for interacting with a file system
    """

    list_files = pyqtSignal(str)
    delete = pyqtSignal(str)
    rename = pyqtSignal(str, str)

    def __init__(self, file_manager, parent=None):
        super().__init__(parent)
        self.path = []
        self.content = []
        self.iconProvider = QFileIconProvider()

        file_manager.on_list_files.connect(self.on_ls)
        file_manager.on_list_fail.connect(self.on_ls_fail)
        file_manager.on_move_file.connect(self.on_mv)
        file_manager.on_move_fail.connect(self.on_mv_fail)
        file_manager.on_delete_file.connect(self.on_delete)
        file_manager.on_delete_fail.connect(self.on_delete_fail)
        self.list_files.connect(file_manager.ls_stat)
        self.delete.connect(file_manager.delete)
        self.rename.connect(file_manager.mv)
        self.invalidate()

    def invalidate(self):
        """
        Invalidates the current content, by doing a new list file operation
        """
        self.list_files.emit("/".join(self.path))

    def on_ls(self, files):
        self.content = files
        if len(self.path) > 0:
            self.content.append(("..", True, 1))
        self.dataChanged.emit(
            self.createIndex(0, 0), self.createIndex(0, len(self.content))
        )

    def on_ls_fail(self):
        """
        Empty the list of files, if list files fails
        """
        self.content = []
        self.dataChanged.emit(self.createIndex(0, 0), self.createIndex(0, 0))

    def on_mv(self, file, new_file):
        self.invalidate()

    def on_mv_fail(self, file, new_file):
        self.invalidate()

    def on_delete(self, file):
        self.invalidate()

    def on_delete_fail(self, file):
        self.invalidate()

    def do_delete(self, file):
        self.delete.emit("/".join(self.path) + "/" + file)
        
    def rowCount(self, parent):
        return len(self.content)

    def columnCount(self, parent):
        return 1

    def is_directory(self, index):
        """
        Is the given index refering to a directory?
        """
        name, is_dir, size = self.content[index.row()]
        return is_dir

    def enter_directory(self, index):
        """
        Move into the given directory
        """
        name, is_dir, size = self.content[index.row()]
        if name == "..":
            self.path.pop()
        elif is_dir:
            self.path.append(name)

        self.list_files.emit("/".join(self.path))
        return self.index(-1)

    def data(self, index, role):
        name, is_directory, size = self.content[index.row()]
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return name
        elif role == Qt.DecorationRole:
            if is_directory:
                icon = self.iconProvider.icon(QFileIconProvider.Folder)
            else:
                icon = self.iconProvider.icon(QFileIconProvider.File)
            return icon

    def get_root_index(self):
        return self.index(-1)

    def flags(self, index):
        """
        Make sure items are editable, to allow renaming, except .. and .
        """
        default_flags = super().flags(index)

        name, is_directory, size = self.content[index.row()]
        if name == ".." or name == ".":
            return default_flags

        return default_flags | Qt.ItemIsEditable

    def setData(self, index, value, role):
        """
        Called when data is changed - in our case when a file/folder is renamed.
        """
        name, is_directory, size = self.content[index.row()]

        if role == Qt.DisplayRole or role == Qt.EditRole:
            path = "/".join(self.path) + "/"

            print("Renaming on device: ", path + name, "to", path + value)
            self.rename.emit(path + name, path + value)
            self.invalidate()
            return True
        return False
