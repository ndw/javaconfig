import os
import pytest
from .context import javaconfig

@pytest.fixture()
def s10_config(request):
    xmlc = os.path.join(os.path.dirname(__file__), 'xmlconfig.xml')
    jc = javaconfig.JavaConfigurations(config=xmlc).config("saxon-10ee")
    return jc

class TestSaxon:

    def test_type(self, s10_config):
        print(s10_config._properties)
        assert s10_config.get_property("type") == "saxon"

    def test_argsep(self, s10_config):
        assert s10_config.get_property("argsep") == ":"

    def test_class(self, s10_config):
        assert s10_config.get_property("class") == "com.saxonica.Transform"

    def test_cp(self, s10_config):
        print(s10_config._properties)
        assert type(s10_config.get_property("classpath")) is list
        cp = s10_config.get_property("classpath")

        assert len(cp) == 3

        if cp[0].endswith("/not-a-jar.jar"):
            assert cp[0].endswith("/test/java/not-a-jar.jar")
            assert cp[1].endswith("/test/java/also-not-a-jar.jar")
        else:
            assert cp[0].endswith("/test/java/also-not-a-jar.jar")
            assert cp[1].endswith("/test/java/not-a-jar.jar")

        assert cp[2].endswith("/test/java/subdir/")
