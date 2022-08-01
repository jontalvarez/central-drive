from PyQt5.QtCore import QCoreApplication, QTimer

list1=[1,2,3,4,5]
delay = 2500

def calling_func():
    if list1:
        list_item = list1.pop()
        QTimer.singleShot(delay, lambda: target_func(list_item))


def target_func(list_item):
    print("fid= ",list_item)
    QTimer.singleShot(delay, calling_func)

app = QCoreApplication([])
calling_func()
app.exec_()