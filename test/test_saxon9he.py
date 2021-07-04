import os
import pytest
from .context import javaconfig

@pytest.fixture()
def s9he_config(request):
    xmlc = os.path.join(os.path.dirname(__file__), 'xmlconfig.xml')
    jc = javaconfig.JavaConfigurations(config=xmlc).config("saxon-9he")
    return jc

class TestSaxon:

    def test_type(self, s9he_config):
        print(s9he_config._properties)
        assert s9he_config.get_property("type") == "saxon"

    def test_argsep(self, s9he_config):
        assert s9he_config.get_property("argsep") == ":"

    def test_class(self, s9he_config):
        assert s9he_config.get_property("class") == "net.sf.saxon.Transform"

    def test_arg(self, s9he_config):
        assert type(s9he_config.get_property("arg")) is list
        arg = s9he_config.get_property("arg")
        assert len(arg) == 4
        assert arg[0]["name"] == "x"
        assert arg[0]["value"] == "org.xmlresolver.tools.ResolvingXMLReader"
        assert arg[1]["name"] == "y"
        assert arg[1]["value"] == "org.xmlresolver.tools.ResolvingXMLReader"
        assert arg[2]["name"] == "r"
        assert arg[2]["value"] == "org.xmlresolver.Resolver"
        assert arg[3]["name"] == "init"
        assert arg[3]["value"] == "docbook.Initializer"

    def test_param(self, s9he_config):
        assert type(s9he_config.get_property("param")) is list
        param = s9he_config.get_property("param")
        assert len(param) == 2
        assert param[0]["name"] == "use.extensions"
        assert param[0]["value"] == "1"
        assert param[1]["name"] == "chunker.output.quiet"
        assert param[1]["value"] == "1"
