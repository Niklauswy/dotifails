"""Code every Wysun Python program shares: paths, atomic files, single instance.

Modules here use the standard library unless their name says otherwise
(``qt_instance``) and never import an application module, so Recorder releases,
the installer runtime and small command-line clients can carry the package as is.
"""
