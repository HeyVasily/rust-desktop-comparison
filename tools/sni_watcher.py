#!/usr/bin/env python3
"""Minimal org.kde.StatusNotifierWatcher for headless Linux shell checks.

Run with the system Python (python3-gi). It plays the role a desktop panel normally
plays: tray libraries register their StatusNotifierItem here, and every registration
is appended to the log given as the first argument as `REGISTER <sender> <argument>`.
It reports a registered host, so clients that wait for one (Qt, AppIndicator) create
their item instead of falling back to XEmbed. It also owns com.canonical.Unity, the
name libunity checks before sending launcher badges, as Unity-compatible docks do;
the badges themselves are observed separately with dbus-monitor.
"""
import sys

from gi.repository import Gio, GLib

XML = """<node><interface name="org.kde.StatusNotifierWatcher">
<method name="RegisterStatusNotifierItem"><arg type="s" direction="in" name="service"/></method>
<method name="RegisterStatusNotifierHost"><arg type="s" direction="in" name="service"/></method>
<property name="RegisteredStatusNotifierItems" type="as" access="read"/>
<property name="IsStatusNotifierHostRegistered" type="b" access="read"/>
<property name="ProtocolVersion" type="i" access="read"/>
<signal name="StatusNotifierItemRegistered"><arg type="s"/></signal>
<signal name="StatusNotifierItemUnregistered"><arg type="s"/></signal>
<signal name="StatusNotifierHostRegistered"/>
</interface></node>"""
PATH = "/StatusNotifierWatcher"
IFACE = "org.kde.StatusNotifierWatcher"

items = []
log = open(sys.argv[1], "a", buffering=1, encoding="utf-8")
node = Gio.DBusNodeInfo.new_for_xml(XML)


def method_call(connection, sender, path, interface, name, parameters, invocation):
    if name == "RegisterStatusNotifierItem":
        argument = parameters.unpack()[0]
        # AppIndicator passes an object path; the item is then <sender><path>.
        item = sender + argument if argument.startswith("/") else argument
        items.append(item)
        log.write(f"REGISTER {sender} {argument}\n")
        connection.emit_signal(None, PATH, IFACE, "StatusNotifierItemRegistered", GLib.Variant("(s)", (item,)))
    invocation.return_value(None)


def get_property(connection, sender, path, interface, name):
    return {
        "RegisteredStatusNotifierItems": GLib.Variant("as", items),
        "IsStatusNotifierHostRegistered": GLib.Variant("b", True),
        "ProtocolVersion": GLib.Variant("i", 0),
    }[name]


def bus_acquired(connection, name):
    connection.register_object(PATH, node.interfaces[0], method_call, get_property, None)


def name_acquired(connection, name):
    log.write(f"OWNED {name}\n")


def name_lost(connection, name):
    log.write(f"LOST {name}\n")
    loop.quit()


Gio.bus_own_name(Gio.BusType.SESSION, IFACE, Gio.BusNameOwnerFlags.NONE, bus_acquired, name_acquired, name_lost)
Gio.bus_own_name(Gio.BusType.SESSION, "com.canonical.Unity", Gio.BusNameOwnerFlags.NONE,
                 None, name_acquired, None)
loop = GLib.MainLoop()
loop.run()
