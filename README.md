# Java Configurations

I run lots of Java (and more broadly, JVM-based) applications. For
many years, I downloaded jar files by hand and constructed little
shell scripts to setup the classpath and other details of the
environment.

Invariably, I’d come back to some application I hadn’t run in a while,
and discover that there were missing jar files or that I had the wrong
versions of jar files. Updating an application almost always lead
to these problems.

That would send me scurrying off across the web to get the new
versions and install them somewhere, then update all the version
numbers in the shell script, then try again. Only to find that the new
versions of dependent libraries had their own updated dependencies.

This is a somewhat self-inflicted problem. There are established
methods for publishing Java applications such that their dependencies,
and the versions of those dependencies, are enumerated in a portable
way.

If you always run Java programs with Maven or in a framework like
Gradle, you can just let the framework sort out the dependencies and
the classpath. But I don’t always find that convenient.

Years ago, I hacked together a Perl script to use Maven to sort out
the dependencies for me. Perl has become unreliable (for me) recently,
so a few weekends ago, I rewrote the script in Python and that’s
what’s checked into this repository.

In brief: the `JavaConfigurations` library works out what complicated
Java command line is required (classpath, properties, classname, etc.)
by reading an XML configuration file and runs it for you.

## Configuration example

The `JavaConfigurations` library begins by reading a configuration
file. The configuration file is an XML document satisfying the
`javaconfig.rnc` grammar. Its described in some detail in
[Configuration summary](#Configuration-summary) below, but we begin
with an illustrative example.

You create a configuration file in XML that looks like this:

```xml
<config>
  <maven-config mvn="/usr/local/bin/mvn"
                dependency-plugin="org.apache.maven.plugins:maven-dependency-plugin:2.1:get">
    <repo>https://repo1.maven.org/maven2</repo>
    <repo>https://oss.sonatype.org/content/repositories/snapshots</repo>
    <repo>https://dev.saxonica.com/maven</repo>
  </maven-config>

  <java xml:id="java" exec="/usr/bin/java">
    <java-option name="XX:+HeapDumpOnOutOfMemoryError"/>
    <system-property name="some-property" value="some-value"/>
  </java>

  <!-- … -->
```

The top-level `maven-config` element is special, it tells the script
where it can find the `mvn` executable and what Maven plugin to run to
resolve dependencies. It contains a list of Maven repositories to
search when trying to find a library.

The rest of the top-level elements are just descriptions of
configurations. Configurations can extend one another, but at the very
bottom there’s going to be one that actually runs java. Each
configuration needs an `xml:id` that uniquely identifies it.

The `exec` attribute identifies the executable that will be run. The
children of a configuration describe various aspects of that
environment. Here we see that the `XX:+HeapDumpOnOutOfMemoryError` option
will be passed to Java and the system property `some-proprty` will have the value `some-value`.
(This translates into `-Dsome-property=some-value` being added to the list of Java
options.)

```xml
  <java xml:id="bigmem" extends="java">
    <java-option name="Xmx1024m"/>
    <envar name="SOME_VAR" value="some value"/>
  </java>
```

The `bigmem` configuration extends `java` (the configuration with the `xml:id` “java”).
It adds a `Xmx1024m` option and an environment variable.

```xml
  <trang xml:id="trang" extends="java"
         class="com.thaiopensource.relaxng.translate.Driver">
    <maven artifact="org.xmlresolver:xmlresolver:3.0.1-SNAPSHOT"/>
    <maven artifact="org.relaxng:trang:20181222"/>
    <maven artifact="org.docbook:docbook-xslTNG:1.5.2"/>
    <maven artifact="org.docbook:schemas-docbook:5.2b10a4"/>
  </trang>
```

The `trang` configuration extends java, specifies the class to run, and
adds Maven artifacts. The script will find and download the artifacts listed, and
any transitive dependencies that they declare, and make sure that they’re all on the
classpath. The `maven` artifacts can be nested, if you want to keep track of what
depends on what in the configuration file.

```xml
  <saxon xml:id="saxon" extends="bigmem">
    <maven artifact="org.xmlresolver:xmlresolver:3.0.1-SNAPSHOT"/>
    <maven artifact="org.docbook:docbook-xslTNG:1.5.2"/>
  </saxon>
```

My `saxon` configuration extends `bigmem`. It doesn’t define a `class`, so you couldn’t
actually run this one, but it puts a couple more libraries into the environment.

```xml
  <saxon xml:id="saxon-9" extends="saxon" class="net.sf.saxon.Transform" argsep=":">
    <arg name="x" value="org.xmlresolver.tools.ResolvingXMLReader"/>
    <arg name="y" value="org.xmlresolver.tools.ResolvingXMLReader"/>
    <arg name="r" value="org.xmlresolver.Resolver"/>
    
    <classpath path="java/*.jar"/>
    <classpath path="java/subdir/"/>
    <classpath path="java/not-a-subdir/"/>
  </saxon>
```
  
The `saxon-9` configuration runs Saxon. It extends `saxon`, adds some arguments,
gets the argument separator, and puts a few more things on the classpath. The Python
script will glob these, so it’ll list each of the jar files.

```xml
  <saxon xml:id="saxon-9he" extends="saxon-9" class="net.sf.saxon.Transform">
    <classpath path="/java/saxonhe-9.9.1.5j/saxon9he.jar"/>
    <arg name="init" value="docbook.Initializer"/>
    <param name="use.extensions" value="1"/>
    <param name="chunker.output.quiet" value="1"/>
  </saxon>
```

This example `saxon-9he` configuration adds the Saxon jar file to the class path, makes
sure the `init` argument is used, and passes some parameters.

The mixture of `arg` and `param` options are really tailored towards running
stylesheets with Saxon. I do that a lot. For other Java applications, you might find
that either of `arg` or `param` are not useful.

```xml
  <saxon xml:id="saxon-10ee" extends="saxon-9" class="com.saxonica.Transform">
    <maven artifact="com.saxonica:Saxon-EE:10.5"/>
    <maven artifact="org.apache.logging.log4j:log4j-api:2.1"/>
    <maven artifact="org.apache.logging.log4j:log4j-core:2.1"/>
    <maven artifact="org.apache.logging.log4j:log4j-slf4j-impl:2.1"/>
    <maven artifact="org.slf4j:jcl-over-slf4j:1.7.10"/>
    <maven artifact="org.slf4j:slf4j-api:1.7.10"/>
    <maven artifact="org.apache.httpcomponents:httpclient:4.5.2"/>
    <maven artifact="org.apache.httpcomponents:httpcore:4.4.5"/>
    <maven artifact="org.apache.httpcomponents:httpmime:4.5.8"/>
  </saxon>
</config>
```

Finally, the `saxon-10ee` configuration gets Saxon EE from Maven and puts a number
of additional artifacts on the classpath.

## Running applications

Once you’ve got `javaconfig` installed and a configuration file setup
(I use `$HOME/.xmlc` by default), you can write a simple shell script
to run the program.

Here’s my `trang` script:

```python
#!/usr/bin/env python3

import sys
from javaconfig import JavaConfigurations

config = JavaConfigurations().config("trang")

config.parse()

resp = config.run()
if resp:
    sys.exit(resp.returncode)
```

The `parse()` method parses `sys.argv` by default, but you can pass a different
array of options if you like. Once parsed, you can run the application.

For something more complicated, here’s my actual `saxon` script.

```python
#!/usr/bin/env python3

import sys
from javaconfig import JavaConfigurations

# XSpec looks for a script named 'saxon' and tries to see if it's the EXPath
# version by running 'saxon --help'. If this script doesn't handle that, I get
# a big blat of error message every time xspec tries to run it. That annoys me,
# so this:
for arg in sys.argv:
    if arg == '--help':
        print("Usage: just like the Saxon command line")
        sys.exit(0)

config = JavaConfigurations().config("saxon-10ee")

config.parse()

showline = "--noshowline" not in config.user_options

for arg in config.arguments:
    if "s" in config.options and "xsl" in config.options:
        print("Cannot interpret bare argument:", arg)
    elif "s" in config.options:
        config.options["xsl"] = arg
    else:
        config.options["s"] = arg
config.arguments = []

if showline:
    if "s" in config.options:
        fn = config.options["s"]
    else:
        fn = ""
    print("-" * 40, fn)

resp = config.run()
if resp:
    sys.exit(resp.returncode)
```

Here you can see how I customize the command line parsing to deal with
an XSpec annoyance and some custom behaviors. I often run `saxon` over
more than one file, so I have the script print a bunch of dashes and
the name of the source file. But I have a special `--noshowline`
option to disable that.

## Configuration summary

The `javaconfig.rnc` schema describes the grammar for configuration
files.

A configuration file is a `config` document that contains a
`maven-config` element and a collection of configurations. It’s a
slightly odd schema in that the configuration element names are
irrelevant and unconstrained. This format grew organically over a
period of many years. I would guess, though I can no longer recall,
that the element names were originally unique and served the same role
as IDs do in the current schema. But I could be wrong.

## Maven configuration

The `maven-config` element has an `mvn` attribute that points to the
local Maven executable and a `dependency-plugin` that identifies the
Maven plugin to use for downloading dependencies from Maven
repositories. You have to have [Maven](https://maven.apache.org/)
installed to use this library.

A list of Maven repositories appear in `repo` elements inside the
`maven-config`. The library will search these repositories in the
specified order to find Java dependencies for applications.

## Application configuration

The remaining elements inside `config` describe the configuration of
applications. There’s a slant towards command line interfaces like
those used by 
[XML Calabash][https://xmlcalabash.com/] and [Saxon][https://www.saxonica.com/].
Which won’t surprise you if you’re familiar with my other projects.

The names of the elements are irrelevant, except that the name
`maven-config` is reserved for the Maven configuration described in
the preceding section. Each configuration must have an `xml:id`
attribute and may have any of the following attributes:

* `exec` identifies the executable to run for this application. This
  usually points to the local installation of Java that you want to
  use for this application.
* `class` identifies the main Java class to run for this application.
* `extends` identifies another configuration (by IDREF)
* `argsep` lets you specify the character that should be used to
  separate program arguments from their values.
  
If one configuration extends another, you can think of the
configuration as having all of the properties of the configuration it
extends, with the *extending* configuration overriding any settings on
the *extended* configuration.

The rules for overriding are that simple atomic values (`class`,
`exec`, etc.) replace the previous value and list values (`classpath`,
`system-property`, etc.) are concatenated.

The children of the configuration element describe its environment:

* `maven` is a (possibly nested) list of Maven artifacts that must be on
  the classpath. `JavaConfigurations` will assure that they’re downloaded, and that
  any artifacts they depend on are downloaded, and that they’re all put on the
  classpath.
* `classpath` is a list of filesystem globs. These will be added to the classpath
  if they exist. (This is how you can add local jar files and classes to the classpath.)
* `java-option` is a list of Java options (these are added to the command line immediately
  after the executable).
* `system-property` is a list of system properties. (Each name/value pair will be added
  to the command line as a `-Dname=value` option after the executable.)
* `envar` is a list of environment variables to be set before running the application.
* `arg` is a list of application arguments. (Each name/value pair will be added to
  the command line as `-name value` where the character between the name and value
  is determined by the `argsep` attribute. These are added *after* the `class`.)
* `param` is a list of application parameters. These probably only
  apply to programs like Saxon and XML Calabash. They’re added as
  `name=value` pairs to the end of the command line.
  
## Running an application

The simplest script for running an application looks like this:

```python
config = JavaConfigurations().config("someID")
config.parse()
config.run()
```

That script finds the configuration with the `xml:id` value `someID`.
That establishes the initial environment. Calling `parse()` parses the
`sys.argv` arguments and adds them to the command line.

The following special rules apply when parsing the arguments:

* If an argument begins with `-D`, it’s assumed to be defining a
  system property.
* If the argument is `--debug`, then debugging is enabled
* If the argument is `--verbose`, then the library becomes a little
  more chatty.
* If the argument is `--nogo`, then the `run()` method will do
  everything up to running the command, then return without running it.  
* Otherwise, if an argument begins with `--`, it’s assumed to be a “user option”.
* If an argument begins with `-`, it’s assumed to be an “arg”.
* If an argument contains an `=`, it’s assumed to be a “param”.
* Otherwise, it’s just stuck on the end of the command line.

After parsing, but before running the command, the configuration can
be modified. The `config` object exposes an API through public
properties. (It’s not the cleanest possible API, but it gets the job
done.)

* `verbose` is a boolean that determines whether or not to be chatty.
* `debug` is a boolean that determines whether or not to run in debug mode.
* `nogo` is a boolean that determines whether or not to actually run the application.
* `java_options` is a list of Java options.
* `system_properties` is a dictionary of system property name/value pairs.
* `envar` is a dictionary of environment variable name/value pairs.
* `options` is a dictionary of option name/value pairs.
* `parameters` is a dictonary of parameter name/value pairs.
* `user_options` is a list of user options, these are other arguments passed to the
  script preceded by `--`. This is a sort of crude mechanism for separating arguments
  intended for the script from arguments intended for the application.
* `arguments` is a list of everything else that will be passed to the application.  

Calling `run()` runs the command. Or does everything except run it if
`nogo` is true. If `debug` is true, this will print out the
environment as parsed and the command line that (would) run.

# Changelog

## Version 0.0.2

The main thrust of this update is to add support for downloading
additional jar files from Maven. The XML Resolver project distributes
both a code jar and a “data” jar. I wanted to be able to specify the
data jar so that it would be added to the classpath.

In Maven lingo, the difference between the code jar and the data jar
is that the latter has a “classifier” value of “data”.

* Updated the maven dependency plugin to version 3.2.0. The previous
  version didn’t seem to support classifiers.
* Reworked how artifacts are parsed so that the classifier can be
  specified:

```
  <maven artifact="org.xmlresolver:xmlresolver:3.0.1" classifier="data"/>
```

* Made the `verbose` option print out a few more diagnostics about
  downloading from Maven.
* Fixed a bug where POM files that had already been downloaded (and hence had
  a `file:` URI) weren’t being parsed.
* Fixed a bug where the classpath could have duplicate jars. I don’t think
  duplicate jars do any harm, but they don’t do any help either!

## Version 0.0.1

Initial release. It’s all new!
