import os
import pytest
from .context import javaconfig

@pytest.fixture()
def trang_config(request):
    xmlc = os.path.join(os.path.dirname(__file__), 'xmlconfig.xml')
    jc = javaconfig.JavaConfigurations(config=xmlc).config("trang")
    return jc

class TestTrang:

    def test_type(self, trang_config):
        assert trang_config.get_property("type") == "trang"

    def test_argsep(self, trang_config):
        assert trang_config.get_property("argsep") is None

    def test_exec(self, trang_config):
        assert trang_config.get_property("exec") == "/usr/bin/java"

    def test_class(self, trang_config):
        assert trang_config.get_property("class") == "com.thaiopensource.relaxng.translate.Driver"

    def test_maven(self, trang_config):
        maven = trang_config.get_property("maven")
        assert maven[0] == "org.xmlresolver:xmlresolver:3.0.1-SNAPSHOT"
        assert maven[1] == "org.relaxng:trang:20181222"
        assert maven[2] == "org.docbook:docbook-xslTNG:1.5.2"
        assert maven[3] == "org.docbook:schemas-docbook:5.2b10a4"

    def test_cp(self, trang_config):
        assert type(trang_config.get_property("classpath")) is list
        assert len(trang_config.get_property("classpath")) == 0

    def test_javaopt(self, trang_config):
        assert type(trang_config.get_property("java-option")) is list
        assert len(trang_config.get_property("java-option")) == 1
        assert trang_config.get_property("java-option")[0] == "XX:+HeapDumpOnOutOfMemoryError"

    def test_system_property(self, trang_config):
        assert type(trang_config.get_property("system-property")) is list
        assert len(trang_config.get_property("system-property")) == 1
        assert(trang_config.get_property("system-property")[0]["value"] == "some-value")

    def test_env(self, trang_config):
        assert type(trang_config.get_property("envar")) is list
        assert len(trang_config.get_property("envar")) == 1
        assert(trang_config.get_property("envar")[0]["name"] == "SOME_VAR")
        assert(trang_config.get_property("envar")[0]["value"] == "some value")

    def test_arg(self, trang_config):
        assert type(trang_config.get_property("arg")) is list
        assert len(trang_config.get_property("arg")) == 0

    def test_param(self, trang_config):
        assert type(trang_config.get_property("param")) is list
        assert len(trang_config.get_property("param")) == 0
