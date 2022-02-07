#!/Usr/bin/env python3

"""Build configurations for Java programs."""

import sys
import os
import re
import glob
import subprocess
import xml.etree.ElementTree as ET
import requests

# I suppose some of the methods could be functions. I don't care.
# pylint: disable=R0201

# There's only one public method. That's all this API needs.
# pylint: disable=R0903

class JavaConfigurations:
    """An API to parse a configuration file and construct Java environments."""

    XML_ID = "{http://www.w3.org/XML/1998/namespace}id"

    def __init__(self, config=None):
        self.repositories = []
        self.maven_plugin = "org.apache.maven.plugins:maven-dependency-plugin:3.2.0:get"
        self.mvn = "/usr/local/bin/mvn"
        self._configurations = {}
        self._tag_parser = {
            "maven": getattr(self, "_parse_maven"),
            "java-option": getattr(self, "_parse_java_option"),
            "classpath": getattr(self, "_parse_classpath"),
            "system-property": getattr(self, "_parse_system_property"),
            "envar": getattr(self, "_parse_envar"),
            "arg": getattr(self, "_parse_arg"),
            "param": getattr(self, "_parse_param"),
        }

        if config is None:
            config = "%s/.xmlc" % os.environ["HOME"]

        self._config = os.path.abspath(config)
        self._configdir = os.path.dirname(self._config)

        tree = ET.ElementTree(file=config)
        root = tree.getroot()
        for node in root:
            if node.tag == "maven-config":
                self._parse_maven_config(node)
            else:
                self._parse_config(node)

    def _parse_config(self, root):
        config = {"type": root.tag}
        if JavaConfigurations.XML_ID in root.attrib:
            config = JavaConfig(
                configId=root.attrib[JavaConfigurations.XML_ID],
                configType=root.tag,
                configurations=self,
            )
        else:
            print("Unreachable configuration without id:", root.tag)
            config = JavaConfig(configId=None, configType=root.tag, configurations=self)

        for prop in root.attrib:
            if prop != JavaConfigurations.XML_ID:
                config.set_property(prop, root.attrib[prop])

        for node in root:
            self._parse_xml(config, node)

        if config.config_id():
            self._configurations[config.config_id()] = config

    def _parse_xml(self, config, node):
        if node.tag in self._tag_parser:
            self._tag_parser[node.tag](config, node)
            for child in node:
                self._parse_xml(config, child)
        else:
            print("Unknown property ignored:", node.tag)

    def _parse_maven_config(self, node):
        if "dependency-plugin" in node.attrib:
            self.maven_plugin = node.attrib["dependency-plugin"]
        if "mvn" in node.attrib:
            self.mvn = node.attrib["mvn"]
        for child in node:
            if child.tag == "repo":
                self.repositories.append(child.text)
            else:
                print("Unrecognized maven configuration:", child.tag)

    def _parse_maven(self, config, node, propname="maven"):
        attrok = True
        if "artifact" in node.attrib:
            try:
                group, artifact, version, classifier = node.attrib["artifact"].split(":")
            except ValueError:
                classifier = None
                group, artifact, version = node.attrib["artifact"].split(":")
        else:
            for attr in ["groupId", "artifactId", "version"]:
                if attr not in node.attrib:
                    # FIXME: better diagnostic required
                    print("Invalid maven artifact configuration")
                    attrok = False
            if attrok:
                group = node.attrib["groupId"]
                artifact = node.attrib["artifactId"]
                version = node.attrib["version"]
                classifier = None

        if attrok and "classifier" in node.attrib:
            classifier = node.attrib["classifier"]

        if classifier is None:
            classifier = ""

        config.set_property(propname, f"{group}:{artifact}:{version}:{classifier}")

    def _parse_java_option(self, config, node, propname="java-option"):
        config.set_property(propname, node.attrib["name"])

    def _parse_classpath(self, config, node, propname="classpath"):
        # Cheap and cheerful absolute path test. Surely this could be
        # improved by some os.path.* magic I can't quite work out.
        abspath = node.attrib["path"]
        if not abspath.startswith("/"):
            abspath = os.path.join(self._configdir, abspath)
        for path in glob.glob(abspath):
            config.set_property(propname, path)

    def _parse_system_property(self, config, node):
        self._parse_kvp(config, node, "system-property")

    def _parse_envar(self, config, node):
        self._parse_kvp(config, node, "envar")

    def _parse_arg(self, config, node):
        self._parse_kvp(config, node, "arg")

    def _parse_param(self, config, node):
        self._parse_kvp(config, node, "param")

    def _parse_kvp(self, config, node, propname):
        config.set_property(
            propname, {"name": node.attrib["name"], "value": node.attrib["value"]}
        )

    def config(self, cfgid, ctype=None):
        """Return the configuration for a particular process."""
        if cfgid not in self._configurations:
            return None

        # Make sure we apply the configurations in the right order,
        # from most distant ancestor forward so that overrides
        # work in the expected way

        idlist = []
        extends = cfgid
        while extends:
            idlist.append(extends)
            if extends in self._configurations:
                parent = self._configurations[extends]
                extends = parent.extends()
            else:
                print("Ignoring unknown parent:", extends)
                extends = None

        config = JavaConfig(configurations=self, configId=cfgid, configType=ctype)

        while idlist:
            refine = self._configurations[idlist.pop()]
            config.merge(refine)

        return config


# There are a lot of instance attributes in this class. But since
# I'm rather cavalierly exposing some of this API by just making
# them public, I'm not going to worry about it.
# pylint: disable=R0902
class JavaConfig:
    """ The configuration for a particular java process. """

    def __init__(self, configurations, configId=None, configType=None):
        self._configurations = configurations
        self._properties = {
            "id": configId,
            "type": configType,
            "argsep": None,
            "exec": None,
            "class": None,
            "extends": None,
            "maven": [],
            "classpath": [],
            "java-option": [],
            "system-property": [],
            "envar": [],
            "arg": [],
            "param": [],
        }
        self._argparse = False
        self.verbose = False
        self.debug = False
        self.nogo = False
        self.java_options = []
        self.system_properties = {}
        self.envar = {}
        self.options = {}
        self.parameters = {}
        self.user_options = []
        self.arguments = []

    def config_id(self):
        """ Return the ID of this configuration. """
        return self._properties["id"]

    def type(self):
        """ Return the configuration type. """
        return self._properties["type"]

    def extends(self):
        """ Return the ID of the configuration that is being extended. """
        return self._properties["extends"]

    def merge(self, refine):
        """ Merge this configuration with the configuration provided. """
        # pylint: disable=W0212

        #print("MERGE:")
        #print(self._properties)
        #print(refine._properties)

        for field in refine._properties:
            if refine._properties[field] is not None:
                self.set_property(field, refine._properties[field])

        self._properties["id"] = None
        self._properties["extends"] = None

    def _merge_lists(self, field, reflist):
        if field not in self._properties:
            # well, that was easy!
            return reflist

        if len(reflist) == 0:
            return self._properties[field]

        # There are two kinds of lists: lists of strings and lists of dictionaries.
        # Lists of dictionaries always have a 'name' key.
        if type(reflist[0]) is dict:
            newlist = []
            lset = set()
            for val in self._properties[field]:
                newlist.append(val)
                lset.add(val["name"])
            for val in reflist:
                if val["name"] not in lset:
                    newlist.append(val)
                    lset.add(val["name"])
            return newlist
        else:
            newlist = []
            lset = set()
            for val in self._properties[field]:
                newlist.append(val)
                lset.add(val)
            for val in reflist:
                if val not in lset:
                    newlist.append(val)
                    lset.add(val)
            return newlist

    def get_property(self, name, default=None):
        """ Return the named property or the default value. """
        if name not in self._properties:
            print("Unknown configuration property:", name)
            return default

        if self._properties[name] is None:
            return default

        return self._properties[name]

    def set_property(self, name, value):
        """ Set the value of the property. """
        if name not in self._properties:
            print("Unknown configuration property ignored:", name)
            return

        if isinstance(self._properties[name], list):
            if isinstance(value, list):
                self._properties[name] += value
            else:
                self._properties[name].append(value)
        else:
            self._properties[name] = value

    def _get_artifacts(self):
        if not self._configurations.repositories:
            raise RuntimeError("No maven repositories configured")

        self._properties["jars"] = []
        for artifact in self._properties["maven"]:
            self._configure_artifact(artifact)

    # This is a complicated, recursive method. I'm ok with that.
    # pylint: disable=R0914, R0912, R0915
    def _configure_artifact(self, artifact, depth=1, pom=None):
        if self.verbose:
            if pom:
                print("Check %s (from %s)" % (artifact, pom))
            else:
                print("Check", artifact)

        try:
            group, artifact, version, classifier = artifact.split(":")
        except ValueError:
            classifier = ""
            group, artifact, version = artifact.split(":")

        if classifier == "":
            jar = "%s-%s.jar" % (artifact, version)
        else:
            jar = "%s-%s-%s.jar" % (artifact, version, classifier)

        jarloc = "%s/.m2/repository/%s/%s/%s/%s" % (
            os.environ["HOME"],
            group.replace(".", "/"),
            artifact,
            version,
            jar
        )

        if os.path.isfile(jarloc):
            self._properties["jars"].append(jarloc)
            return

        if self.verbose:
            print("Download:", jar)

        repo = None
        for check in self._configurations.repositories:
            pom = "%s/%s/%s/%s-%s.pom" % (
                group.replace(".", "/"),
                artifact,
                version,
                artifact,
                version,
            )

            if self.verbose:
                print(f"Repo: {check}")

            if check.startswith("file:"):
                filename = "/%s/%s" % (re.sub("^file:/+", "", check), pom)

                if self.verbose:
                    print(f"File: {filename}")

                if os.path.isfile(filename):
                    repo = check
            else:
                uri = "%s/%s" % (check, pom)

                if self.verbose:
                    print(f"URI: {uri}")

                resp = requests.head(uri, allow_redirects=True)
                if resp.status_code == 200:
                    repo = check
                elif resp.status_code == 404:
                    pass
                else:
                    print(resp.status_code, "from", uri)

            if repo:
                break

        if not repo:
            print("Cannot find", pom)
            return


        mvn_args = [self._configurations.mvn,
                    self._configurations.maven_plugin,
                    "-DremoteRepositories=%s" % repo,
                    "-DgroupId=%s" % group,
                    "-DartifactId=%s" % artifact,
                    "-Dversion=%s" % version]
        if classifier != "":
            mvn_args.append("-Dclassifier=%s" % classifier)

        if self.verbose:
            print("Run: ", " ".join(mvn_args))

        resp = subprocess.run(mvn_args,
                              capture_output=False, check=False
                              )

        if resp.returncode != 0:
            print("Maven dependency download failed?")

        if not os.path.exists(jarloc):
            print("Failed to download %s:%s:%s" % (group, artifact, version))
            return


        pom_file = "%s/%s" % (repo, pom);
        if pom_file.startswith("file:/"):
            pom_file = pom_file[6:]
            try:
                with open(pom_file) as pom_data:
                    resp = "\n".join(pom_data.readlines());
            except FileNotFoundError:
                print("Cannot read POM: %s/%s" % (repo, pom))
                return
        else:
            resp = requests.get(pom_file);
            if resp.status_code == 200:
                resp = resp.text
            else:
                print("Cannot download POM: %s/%s" % (repo, pom))
                return

        tree = ET.fromstring(resp)
        dependencies = tree.find("{http://maven.apache.org/POM/4.0.0}dependencies")
        if dependencies:
            for dependency in dependencies.findall("{http://maven.apache.org/POM/4.0.0}dependency"):
                dgroup = self._pom_text(dependency, "groupId")
                dartifact = self._pom_text(dependency, "artifactId")
                dversion = self._pom_text(dependency, "version")
                dscope = self._pom_text(dependency, "scope")

                if not dversion:
                    dversion = version

                if depth > 0 and dscope != "test" and dscope != "provided":
                    artifact = "%s:%s:%s" % (dgroup, dartifact, dversion)
                    self._configure_artifact(artifact, depth - 1, pom=pom)

    def _pom_text(self, node, name):
        value = node.find("{http://maven.apache.org/POM/4.0.0}%s" % name)
        if value is None:
            return None
        return value.text

    def _parse_arg(self, name, hashmap, sep=None):
        value = None

        # For convenience, treat the first of ":" or "=" as a separator
        if sep is None:
            if ":" in name:
                sep = ":"
            if "=" in name:
                if ":" not in name or name.index("=") < name.index(":"):
                    sep = "="

        if sep and sep in name:
            pos = name.index(sep)
            value = name[pos + 1 :]
            name = name[0:pos]
        if name in hashmap:
            if isinstance(hashmap[name], list):
                hashmap[name].append(value)
            else:
                hashmap[name] = [hashmap[name], value]
        else:
            hashmap[name] = value

    def parse(self, args=None):
        """ Parse the arguments provided. Defaults to sys.argv[1:]. """

        self._argparse = True

        if not args:
            args = sys.argv[1:]

        for arg in args:
            if arg.startswith("-D"):
                self._parse_arg(arg[2:], self.system_properties)
            elif arg.startswith("--"):
                if arg == "--debug":
                    self.debug = True
                elif arg == "--verbose":
                    self.verbose = True
                elif arg == "--nogo":
                    self.nogo = True
                else:
                    self.user_options.append(arg)
            elif arg.startswith("-"):
                self._parse_arg(arg[1:], self.options)
            elif "=" in arg:
                self._parse_arg(arg, self.parameters)
            else:
                self.arguments.append(arg)

    def run(self):
        """ Run the process. """

        if not self.get_property("class"):
            raise RuntimeError("No class defined")

        self._get_artifacts()
        if not self.get_property("exec"):
            raise RuntimeError("No executable specified")
        else:
            # Is exec a real thing?
            epath = os.path.join(self._configurations._configdir, self.get_property("exec"))
            if not os.path.exists(epath):
                raise RuntimeError("Specified executable does not exist")

        if not self._argparse:
            self.parse()

        sys_prop_names = self.system_properties.keys()
        for prop in self.get_property("system-property"):
            if prop["name"] not in sys_prop_names:
                self._parse_arg(
                    "%s=%s" % (prop["name"], prop["value"]), self.system_properties,
                    sep="=")
        sys_props = []
        for name in self.system_properties:
            vlist = self.system_properties[name]
            if not isinstance(vlist, list):
                vlist = [vlist]
            for value in vlist:
                if value is None:
                    sys_props.append("-D%s" % name)
                else:
                    sys_props.append("-D%s=%s" % (name, value))

        option_names = self.options.keys()
        for arg in self.get_property("arg"):
            if arg["name"] not in option_names:
                self._parse_arg("%s:%s" % (arg["name"], arg["value"]), self.options,
                                sep=":")
        user_args = []
        argsep = self.get_property("argsep", ":")
        for name in self.options:
            vlist = self.options[name]
            if not isinstance(vlist, list):
                vlist = [vlist]
            for value in vlist:
                if value is None:
                    user_args.append("-%s" % name)
                else:
                    user_args.append("-%s%s%s" % (name, argsep, value))

        param_names = self.parameters.keys()
        for name in self.parameters:
            if name not in param_names:
                self._parse_arg("%s=%s" % (name, param_names[name]), self.parameters,
                                sep="=")
        user_params = []
        for name in self.parameters:
            vlist = self.parameters[name]
            if not isinstance(vlist, list):
                vlist = [vlist]
            for value in vlist:
                user_params.append("%s=%s" % (name, value))

        java_options = []
        for prop in self.get_property("java-option"):
            java_options.append("-%s" % prop)

        classpath = []
        if self.get_property("classpath") or self.get_property("jars"):
            cpset = set()
            for path in self.get_property("classpath") + self.get_property("jars"):
                if path not in cpset:
                    classpath.append(path);
                    cpset.add(path);

        process = self.get_property("exec")
        classname = self.get_property("class")

        if self.verbose:
            self._showconfig(
                process,
                classname,
                sys_props,
                user_args,
                user_params,
                java_options,
                classpath,
            )

        command = [process] + sys_props + ["-cp", ":".join(classpath)]
        command += [classname] + user_args + user_params + self.arguments

        if self.debug:
            print(command)

        if self.nogo:
            return None

        env = os.environ.copy()
        for prop in self.get_property("envar"):
            env[prop["name"]] = prop["value"]

        return subprocess.run(command, env=env,
                              capture_output=False, check=False)

    # This is a debugging method. It has a lotof arguments, but I don't care.
    # pylint: disable=R0913
    def _showconfig(self, process, classname, sys_props,
                    user_args, user_params, java_options, classpath):
        print(process)
        for opt in java_options:
            print("\t%s" % opt)
        if sys_props:
            for prop in sys_props:
                print("\t%s" % prop)
        if classpath:
            print("Classpath:")
            for path in classpath:
                print("\t%s" % path)
        print(classname)
        if user_args:
            for arg in user_args:
                if arg != "--nogo":
                    print("\t%s" % arg)
        if user_params:
            for param in user_params:
                print("\t%s" % param)
        for arg in self.arguments:
            print("\t%s" % arg)
