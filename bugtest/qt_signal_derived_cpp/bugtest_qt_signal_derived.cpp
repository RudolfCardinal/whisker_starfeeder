// bugtest_qt_signal_derived.cpp

#include "bugtest_qt_signal_derived.h"
#include <unistd.h>  // for sleep()


void debug_object(const QString& obj_name, const QObject& obj)
{
    qDebug() << "Object" << obj_name << "belongs to QThread" << obj.thread();
}


void debug_thread(const QString& thread_name, const QThread& thread)
{
    qDebug() << thread_name << "is QThread at" << &thread;
}


void report(const QString& msg)
{
    qDebug().nospace() << msg << " [" << QThread::currentThreadId() << "]";
}

void Transmitter::start()
{
    unsigned int count = 3;
    report("Starting transmitter");
    while (count > 0) {
        sleep(1);  // seconds
        report(QString("transmitting, count=%1").arg(count));
        emit transmit();
        count -= 1;
    }
    report("Stopping transmitter");
    emit finished();
}


void Base::start()
{
    report("Starting receiver");
}


void Base::receive()
{
    report("receive: BASE");
}


void Derived::receive()
{
    report("receive: DERIVED");
}

#define USE_DERIVED


int main(int argc, char* argv[])
{
    // Objects
    QCoreApplication app(argc, argv);

    QThread tx_thread;
    debug_thread("tx_thread", tx_thread);
    Transmitter transmitter;
    debug_object("transmitter", transmitter);
    transmitter.moveToThread(&tx_thread);
    debug_object("transmitter", transmitter);

    QThread rx_thread;
    debug_thread("rx_thread", rx_thread);
#ifdef USE_DERIVED
    Derived receiver;
#else
    Base receiver;
#endif
    debug_object("receiver", receiver);
    receiver.moveToThread(&rx_thread);
    debug_object("receiver", receiver);

    // Signals: startup
    QObject::connect(&tx_thread, SIGNAL(started()),
                     &transmitter, SLOT(start()));    
    QObject::connect(&rx_thread, SIGNAL(started()),
                     &receiver, SLOT(start()));    
    // ... shutdown
    QObject::connect(&transmitter, SIGNAL(finished()),
                     &tx_thread, SLOT(quit()));    
    QObject::connect(&tx_thread, SIGNAL(finished()),
                     &rx_thread, SLOT(quit()));    
    QObject::connect(&rx_thread, SIGNAL(finished()),
                     &app, SLOT(quit()));    
    // ... action
    QObject::connect(&transmitter, SIGNAL(transmit()),
                     &receiver, SLOT(receive()));    

    // Go
    rx_thread.start();
    tx_thread.start();
    report("Starting app");
    return app.exec();
}
