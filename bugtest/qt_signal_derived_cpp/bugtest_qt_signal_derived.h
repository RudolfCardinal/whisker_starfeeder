// bugtest_qt_signal_derived.h

/*

http://stackoverflow.com/questions/34125065/derived-classes-receiving-signals-in-wrong-thread-in-pyside-qt-pyqt

To build:
    qmake -project
    qmake -makefile
    make
*/

#include <QtCore/QCoreApplication>
#include <QtCore/QtDebug>  // not QDebug
#include <QtCore/QObject>
#include <QtCore/QString>  // works with qDebug where std::string doesn't
#include <QtCore/QThread>


void debug_object(const QString& obj_name, const QObject& obj);
void debug_thread(const QString& thread_name, const QThread& thread);
void report(const QString& msg);
class Transmitter : public QObject
{
    Q_OBJECT  // enables macros like "signals:", "slots:", "emit"
public:
    Transmitter() {}
    virtual ~Transmitter() {}
signals:
    void transmit();
    void finished();
public slots:
    void start();
};


class Base : public QObject
{
    Q_OBJECT
public:
    Base() {}
public slots:
    void start();
    void receive();
};


class Derived : public Base
{
    Q_OBJECT
public:
    Derived() {}
public slots:
    void receive();
};
