// Optional shell-integration checks: CMake -DVERANDA_SHELL_CHECKS=ON, active only when
// COMPARISON_SHELL_CHECKS is set. Each check prints a `SHELL {json}` line that
// tools/shell_probe.py verifies from outside the app.
#pragma once

#include <QApplication>
#include <QColor>
#include <QIcon>
#include <QImage>
#include <QLocalServer>
#include <QLocalSocket>
#include <QMenu>
#include <QPixmap>
#include <QSystemTrayIcon>
#include <QTimer>
#include <QWidget>
#include <iostream>

namespace shell {

inline bool enabled() { return qEnvironmentVariableIsSet("COMPARISON_SHELL_CHECKS"); }

inline void report(const char *check, const char *status, QString detail) {
    detail.replace("\\", "\\\\").replace("\"", "\\\"");
    std::cout << "SHELL {\"check\":\"" << check << "\",\"status\":\"" << status
              << "\",\"detail\":\"" << detail.toStdString() << "\"}" << std::endl;
}

inline QString serverName() { return QStringLiteral("veranda-shell-qt"); }

// Qt 6 has no single-application class; this is the usual QLocalServer pattern.
inline bool handedToRunningInstance() {
    if (!enabled()) return false;
    QLocalSocket socket;
    socket.connectToServer(serverName());
    if (!socket.waitForConnected(500)) return false;
    socket.write("activate");
    socket.waitForBytesWritten(500);
    report("single-instance", "second-exits", "QLocalSocket reached the running instance");
    return true;
}

inline QIcon trayIcon() {
    QImage image(32, 32, QImage::Format_RGBA8888);
    image.fill(Qt::white);
    for (int y = 3; y < 29; ++y)
        for (int x = 3; x < 29; ++x) image.setPixelColor(x, y, QColor(42, 120, 214));
    return QIcon(QPixmap::fromImage(image));
}

class Checks : public QObject {
public:
    explicit Checks(QWidget *window) {
        QLocalServer::removeServer(serverName());
        if (server.listen(serverName()))
            report("single-instance", "primary", "QLocalServer");
        else
            report("single-instance", "error", server.errorString());
        connect(&server, &QLocalServer::newConnection, this, [this, window] {
            if (auto *connection = server.nextPendingConnection()) connection->deleteLater();
            report("single-instance", "forwarded", "QLocalServer connection from a second launch");
            window->raise();
        });

        if (!QSystemTrayIcon::isSystemTrayAvailable())
            report("tray", "no-host", "QSystemTrayIcon::isSystemTrayAvailable() is false");
        menu.addAction("Show window", [] { report("tray", "menu", "show"); });
        menu.addAction("Quit", [] { report("tray", "menu", "quit"); });
        tray.setIcon(trayIcon());
        tray.setToolTip("Veranda shell check");
        tray.setContextMenu(&menu);
        connect(&tray, &QSystemTrayIcon::activated, this, [](QSystemTrayIcon::ActivationReason reason) {
            report("tray", "click", QString("activated reason %1").arg(int(reason)));
        });
        tray.show();
        report("tray", tray.isVisible() ? "created" : "error", "QSystemTrayIcon");

#if QT_VERSION >= QT_VERSION_CHECK(6, 5, 0)
        qApp->setBadgeNumber(3);
        report("badge", "set", "QGuiApplication::setBadgeNumber");
#else
        report("badge", "no-api", "QGuiApplication::setBadgeNumber needs Qt 6.5; built with " QT_VERSION_STR);
#endif
        report("hotkey", "no-api", "Qt has no global shortcut API (third-party QHotkey)");

        bool ok = false;
        int seconds = qEnvironmentVariableIntValue("COMPARISON_SHELL_ATTENTION_DELAY", &ok);
        QTimer::singleShot((ok ? seconds : 12) * 1000, window, [window] {
            QApplication::alert(window, 0);
            report("attention", "requested", "QApplication::alert");
        });
    }

private:
    QLocalServer server;
    QMenu menu;
    QSystemTrayIcon tray;
};

}  // namespace shell
