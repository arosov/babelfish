<!-- SOURCE: https://docs.python.org/3/library/asyncio.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
#### Previous topic
[Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html "previous chapter")
#### Next topic
[Runners](https://docs.python.org/3/library/asyncio-runner.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio.rst?plain=1)


### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-runner.html "Runners") |
  * [previous](https://docs.python.org/3/library/ipc.html "Networking and Interprocess Communication") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html)
  * | 
  * Theme  Auto Light Dark |


#  `asyncio` — Asynchronous I/O[¶](https://docs.python.org/3/library/asyncio.html#module-asyncio "Link to this heading")
* * *
Hello World!
Copy```
import asyncio

async def main():
    print('Hello ...')
    await asyncio.sleep(1)
    print('... World!')

asyncio.run(main())

```

asyncio is a library to write **concurrent** code using the **async/await** syntax.
asyncio is used as a foundation for multiple Python asynchronous frameworks that provide high-performance network and web-servers, database connection libraries, distributed task queues, etc.
asyncio is often a perfect fit for IO-bound and high-level **structured** network code.
See also 

[A Conceptual Overview of asyncio](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#a-conceptual-overview-of-asyncio)
    
Explanation of the fundamentals of asyncio.
asyncio provides a set of **high-level** APIs to:
  * [run Python coroutines](https://docs.python.org/3/library/asyncio-task.html#coroutine) concurrently and have full control over their execution;
  * perform [network IO and IPC](https://docs.python.org/3/library/asyncio-stream.html#asyncio-streams);
  * control [subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio-subprocess);
  * distribute tasks via [queues](https://docs.python.org/3/library/asyncio-queue.html#asyncio-queues);
  * [synchronize](https://docs.python.org/3/library/asyncio-sync.html#asyncio-sync) concurrent code;


Additionally, there are **low-level** APIs for _library and framework developers_ to:
  * create and manage [event loops](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio-event-loop), which provide asynchronous APIs for [networking](https://docs.python.org/3/library/asyncio-eventloop.html#loop-create-server), running [subprocesses](https://docs.python.org/3/library/asyncio-eventloop.html#loop-subprocess-exec), handling [OS signals](https://docs.python.org/3/library/asyncio-eventloop.html#loop-add-signal-handler), etc;
  * implement efficient protocols using [transports](https://docs.python.org/3/library/asyncio-protocol.html#asyncio-transports-protocols);
  * [bridge](https://docs.python.org/3/library/asyncio-future.html#asyncio-futures) callback-based libraries and code with async/await syntax.


[Availability](https://docs.python.org/3/library/intro.html#availability): not WASI.
This module does not work or is not available on WebAssembly. See [WebAssembly platforms](https://docs.python.org/3/library/intro.html#wasm-availability) for more information.
asyncio REPL
You can experiment with an `asyncio` concurrent context in the [REPL](https://docs.python.org/3/glossary.html#term-REPL):
Copy```
$ python -m asyncio
asyncio REPL ...
Use "await" directly instead of "asyncio.run()".
Type "help", "copyright", "credits" or "license" for more information.
>>> import asyncio
>>> await asyncio.sleep(10, result='hello')
'hello'

```

This REPL provides limited compatibility with [`PYTHON_BASIC_REPL`](https://docs.python.org/3/using/cmdline.html#envvar-PYTHON_BASIC_REPL). It is recommended that the default REPL is used for full functionality and the latest features.
Raises an [auditing event](https://docs.python.org/3/library/sys.html#auditing) `cpython.run_stdin` with no arguments.
Changed in version 3.12.5: (also 3.11.10, 3.10.15, 3.9.20, and 3.8.20) Emits audit events.
Changed in version 3.13: Uses PyREPL if possible, in which case [`PYTHONSTARTUP`](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONSTARTUP) is also executed. Emits audit events.
Reference
High-level APIs
  * [Runners](https://docs.python.org/3/library/asyncio-runner.html)
  * [Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html)
  * [Streams](https://docs.python.org/3/library/asyncio-stream.html)
  * [Synchronization Primitives](https://docs.python.org/3/library/asyncio-sync.html)
  * [Subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html)
  * [Queues](https://docs.python.org/3/library/asyncio-queue.html)
  * [Exceptions](https://docs.python.org/3/library/asyncio-exceptions.html)
  * [Call Graph Introspection](https://docs.python.org/3/library/asyncio-graph.html)


Low-level APIs
  * [Event Loop](https://docs.python.org/3/library/asyncio-eventloop.html)
  * [Futures](https://docs.python.org/3/library/asyncio-future.html)
  * [Transports and Protocols](https://docs.python.org/3/library/asyncio-protocol.html)
  * [Policies](https://docs.python.org/3/library/asyncio-policy.html)
  * [Platform Support](https://docs.python.org/3/library/asyncio-platforms.html)
  * [Extending](https://docs.python.org/3/library/asyncio-extending.html)


Guides and Tutorials
  * [High-level API Index](https://docs.python.org/3/library/asyncio-api-index.html)
  * [Low-level API Index](https://docs.python.org/3/library/asyncio-llapi-index.html)
  * [Developing with asyncio](https://docs.python.org/3/library/asyncio-dev.html)


Note
The source code for asyncio can be found in [Lib/asyncio/](https://github.com/python/cpython/tree/3.14/Lib/asyncio/).
#### Previous topic
[Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html "previous chapter")
#### Next topic
[Runners](https://docs.python.org/3/library/asyncio-runner.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio.rst?plain=1)


«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-runner.html "Runners") |
  * [previous](https://docs.python.org/3/library/ipc.html "Networking and Interprocess Communication") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 


---

<!-- SOURCE: https://docs.python.org/3/bugs.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
### [Table of Contents](https://docs.python.org/3/contents.html)
  * [Dealing with Bugs](https://docs.python.org/3/bugs.html)
    * [Documentation bugs](https://docs.python.org/3/bugs.html#documentation-bugs)
    * [Using the Python issue tracker](https://docs.python.org/3/bugs.html#using-the-python-issue-tracker)
    * [Getting started contributing to Python yourself](https://docs.python.org/3/bugs.html#getting-started-contributing-to-python-yourself)


#### Previous topic
[About this documentation](https://docs.python.org/3/about.html "previous chapter")
#### Next topic
[Copyright](https://docs.python.org/3/copyright.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/bugs.rst?plain=1)


### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/copyright.html "Copyright") |
  * [previous](https://docs.python.org/3/about.html "About this documentation") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [Dealing with Bugs](https://docs.python.org/3/bugs.html)
  * | 
  * Theme  Auto Light Dark |


# Dealing with Bugs[¶](https://docs.python.org/3/bugs.html#dealing-with-bugs "Link to this heading")
Python is a mature programming language which has established a reputation for stability. In order to maintain this reputation, the developers would like to know of any deficiencies you find in Python.
It can be sometimes faster to fix bugs yourself and contribute patches to Python as it streamlines the process and involves less people. Learn how to [contribute](https://docs.python.org/3/bugs.html#contributing-to-python).
## Documentation bugs[¶](https://docs.python.org/3/bugs.html#documentation-bugs "Link to this heading")
If you find a bug in this documentation or would like to propose an improvement, please submit a bug report on the [issue tracker](https://docs.python.org/3/bugs.html#using-the-tracker). If you have a suggestion on how to fix it, include that as well.
You can also open a discussion item on our [Documentation Discourse forum](https://discuss.python.org/c/documentation/26).
If you find a bug in the theme (HTML / CSS / JavaScript) of the documentation, please submit a bug report on the [python-doc-theme issue tracker](https://github.com/python/python-docs-theme).
See also 

[Documentation bugs](https://github.com/python/cpython/issues?q=is%3Aissue+is%3Aopen+label%3Adocs)
    
A list of documentation bugs that have been submitted to the Python issue tracker. 

[Issue Tracking](https://devguide.python.org/tracker/)
    
Overview of the process involved in reporting an improvement on the tracker. 

[Helping with Documentation](https://devguide.python.org/docquality/#helping-with-documentation)
    
Comprehensive guide for individuals that are interested in contributing to Python documentation. 

[Documentation Translations](https://devguide.python.org/documentation/translating/)
    
A list of GitHub pages for documentation translation and their primary contacts.
## Using the Python issue tracker[¶](https://docs.python.org/3/bugs.html#using-the-python-issue-tracker "Link to this heading")
Issue reports for Python itself should be submitted via the GitHub issues tracker (<https://github.com/python/cpython/issues>). The GitHub issues tracker offers a web form which allows pertinent information to be entered and submitted to the developers.
The first step in filing a report is to determine whether the problem has already been reported. The advantage in doing so, aside from saving the developers’ time, is that you learn what has been done to fix it; it may be that the problem has already been fixed for the next release, or additional information is needed (in which case you are welcome to provide it if you can!). To do this, search the tracker using the search box at the top of the page.
If the problem you’re reporting is not already in the list, log in to GitHub. If you don’t already have a GitHub account, create a new account using the “Sign up” link. It is not possible to submit a bug report anonymously.
Being now logged in, you can submit an issue. Click on the “New issue” button in the top bar to report a new issue.
The submission form has two fields, “Title” and “Comment”.
For the “Title” field, enter a _very_ short description of the problem; fewer than ten words is good.
In the “Comment” field, describe the problem in detail, including what you expected to happen and what did happen. Be sure to include whether any extension modules were involved, and what hardware and software platform you were using (including version information as appropriate).
Each issue report will be reviewed by a developer who will determine what needs to be done to correct the problem. You will receive an update each time an action is taken on the issue.
See also 

[How to Report Bugs Effectively](https://www.chiark.greenend.org.uk/~sgtatham/bugs.html)
    
Article which goes into some detail about how to create a useful bug report. This describes what kind of information is useful and why it is useful. 

[Bug Writing Guidelines](https://bugzilla.mozilla.org/page.cgi?id=bug-writing.html)
    
Information about writing a good bug report. Some of this is specific to the Mozilla project, but describes general good practices.
## Getting started contributing to Python yourself[¶](https://docs.python.org/3/bugs.html#getting-started-contributing-to-python-yourself "Link to this heading")
Beyond just reporting bugs that you find, you are also welcome to submit patches to fix them. You can find more information on how to get started patching Python in the [Python Developer’s Guide](https://devguide.python.org/). If you have questions, the [core-mentorship mailing list](https://mail.python.org/mailman3/lists/core-mentorship.python.org/) is a friendly place to get answers to any and all questions pertaining to the process of fixing issues in Python.
### [Table of Contents](https://docs.python.org/3/contents.html)
  * [Dealing with Bugs](https://docs.python.org/3/bugs.html)
    * [Documentation bugs](https://docs.python.org/3/bugs.html#documentation-bugs)
    * [Using the Python issue tracker](https://docs.python.org/3/bugs.html#using-the-python-issue-tracker)
    * [Getting started contributing to Python yourself](https://docs.python.org/3/bugs.html#getting-started-contributing-to-python-yourself)


#### Previous topic
[About this documentation](https://docs.python.org/3/about.html "previous chapter")
#### Next topic
[Copyright](https://docs.python.org/3/copyright.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/bugs.rst?plain=1)


«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/copyright.html "Copyright") |
  * [previous](https://docs.python.org/3/about.html "About this documentation") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [Dealing with Bugs](https://docs.python.org/3/bugs.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 


---

<!-- SOURCE: https://www.python.org -->
**Notice:** This page displays a fallback because interactive scripts did not run. Possible causes include disabled JavaScript or failure to load scripts or stylesheets.
[Skip to content](https://www.python.org/#content "Skip to content")
[ ▼ Close ](https://www.python.org/#python-network)
  * [Python](https://www.python.org/ "The Python Programming Language")
  * [PSF](https://www.python.org/psf/ "The Python Software Foundation")
  * [Docs](https://docs.python.org "Python Documentation")
  * [PyPI](https://pypi.org/ "Python Package Index")
  * [Jobs](https://www.python.org/jobs/ "Python Job Board")
  * [Community](https://www.python.org/community/)

[ ▲ The Python Network ](https://www.python.org/#top)
[![python™](https://www.python.org/static/img/python-logo.png)](https://www.python.org/)
[Donate](https://donate.python.org/)
[≡ Menu](https://www.python.org/#site-map) Search This Site GO 
  * [**A A**](https://www.python.org/)
    * [Smaller](javascript:; "Make Text Smaller")
    * [Larger](javascript:; "Make Text Larger")
    * [Reset](javascript:; "Reset any font size changes I have made")


  * [Socialize](https://www.python.org/)
    * [](https://www.linkedin.com/company/python-software-foundation/)
    * [](https://fosstodon.org/@ThePSF)
    * [](https://www.python.org/community/irc/)
    * [](https://twitter.com/ThePSF)


  * [Sign In](https://www.python.org/accounts/login/ "Sign Up or Sign In to Python.org")
    * [Sign Up / Register](https://www.python.org/accounts/signup/)
    * [Sign In](https://www.python.org/accounts/login/)


  * [About](https://www.python.org/about/)
    * [Applications](https://www.python.org/about/apps/)
    * [Quotes](https://www.python.org/about/quotes/)
    * [Getting Started](https://www.python.org/about/gettingstarted/)
    * [Help](https://www.python.org/about/help/)
    * [Python Brochure](http://brochure.getpython.info/)
    * #### Python is a programming language that lets you work more quickly and integrate your systems more effectively.
You can learn to use Python and see almost immediate gains in productivity and lower maintenance costs. [Learn more about Python](https://www.python.org/about). 
  * [Downloads](https://www.python.org/downloads/)
    * [All releases](https://www.python.org/downloads/)
    * [Source code](https://www.python.org/downloads/source/)
    * [Windows](https://www.python.org/downloads/windows/)
    * [macOS](https://www.python.org/downloads/macos/)
    * [Android](https://www.python.org/downloads/android/)
    * [Other Platforms](https://www.python.org/download/other/)
    * [License](https://docs.python.org/3/license.html)
    * [Alternative Implementations](https://www.python.org/download/alternatives)
    * ### Python Source
[Python 3.14.3](https://www.python.org/ftp/python/3.14.3/Python-3.14.3.tar.xz)
Not the OS you are looking for? Python can be used on many operating systems and environments. [View the full list of downloads](https://www.python.org/downloads/).
#### Download for Windows
[Python install manager](https://www.python.org/ftp/python/pymanager/python-manager-25.2.msix)
Or get the standalone installer for [Python 3.14.3](https://www.python.org/ftp/python/3.14.3/python-3.14.3-amd64.exe)
Not the OS you are looking for? Python can be used on many operating systems and environments. [View the full list of downloads](https://www.python.org/downloads/).
#### Download for macOS
[Python 3.14.3](https://www.python.org/ftp/python/3.14.3/python-3.14.3-macos11.pkg)
Not the OS you are looking for? Python can be used on many operating systems and environments. [View the full list of downloads](https://www.python.org/downloads/).
#### Download Python for Any OS
Python can be used on many operating systems and environments.
[View the full list of downloads](https://www.python.org/downloads/operating-systems/)
  * [Documentation](https://www.python.org/doc/)
    * [Docs](https://www.python.org/doc/)
    * [Audio/Visual Talks](https://www.python.org/doc/av)
    * [Beginner's Guide](https://wiki.python.org/moin/BeginnersGuide)
    * [FAQ](https://docs.python.org/3/faq/)
    * [Non-English Docs](https://translations.python.org/)
    * [PEP Index](https://peps.python.org)
    * [Python Books](https://wiki.python.org/moin/PythonBooks)
    * [Python Essays](https://www.python.org/doc/essays/)
    * #### Python’s standard documentation: download, browse or watch a tutorial.
Get started below, or visit the [Documentation page to browse by version](https://www.python.org/doc/versions/). 
  

[Python Docs](https://docs.python.org/3/)
  * [Community](https://www.python.org/community/)
    * [Diversity](https://www.python.org/community/diversity/)
    * [Mailing Lists](https://www.python.org/community/lists/)
    * [IRC](https://www.python.org/community/irc/)
    * [Forums](https://www.python.org/community/forums/)
    * [PSF Annual Impact Report](https://www.python.org/psf/annual-report/2024/)
    * [Python Conferences](https://www.python.org/community/workshops/)
    * [Special Interest Groups](https://www.python.org/community/sigs/)
    * [Python Logo](https://www.python.org/community/logos/)
    * [Python Wiki](https://wiki.python.org/moin/)
    * [Code of Conduct](https://www.python.org/psf/conduct/)
    * [Community Awards](https://www.python.org/community/awards)
    * [Get Involved](https://www.python.org/psf/get-involved/)
    * [Shared Stories](https://www.python.org/psf/community-stories/)
    * #### The Python Community
Great software is supported by great people. Our user base is enthusiastic, dedicated to encouraging use of the language, and committed to being diverse and friendly.
  * [Success Stories](https://www.python.org/success-stories/ "success-stories")
    * [Arts](https://www.python.org/success-stories/category/arts/)
    * [Business](https://www.python.org/success-stories/category/business/)
    * [Education](https://www.python.org/success-stories/category/education/)
    * [Engineering](https://www.python.org/success-stories/category/engineering/)
    * [Government](https://www.python.org/success-stories/category/government/)
    * [Scientific](https://www.python.org/success-stories/category/scientific/)
    * [Software Development](https://www.python.org/success-stories/category/software-development/)
    * > Want to know how Python is performing on Arm across Linux, Windows, and the cloud? Our 2025 update highlights the latest JIT improvements, ecosystem milestones like GitHub runners and PyTorch on Windows, and the continued collaboration driving it all forward. 
Diego Russo, [Arm Ltd](https://www.arm.com)
  * [News](https://www.python.org/blogs/ "News from around the Python world")
    * [Python News](https://www.python.org/blogs/ "Python Insider Blog Posts")
    * [PSF Newsletter](https://www.python.org/psf/newsletter/ "Python Software Foundation Newsletter")
    * [PSF News](http://pyfound.blogspot.com/ "PSF Blog")
    * [PyCon US News](http://pycon.blogspot.com/ "PyCon Blog")
    * [News from the Community](http://planetpython.org/ "Planet Python")
  * [Events](https://www.python.org/events/)
    * [Python Events](https://www.python.org/events/python-events/)
    * [User Group Events](https://www.python.org/events/python-user-group/)
    * [Python Events Archive](https://www.python.org/events/python-events/past/)
    * [User Group Events Archive](https://www.python.org/events/python-user-group/past/)
    * [Submit an Event](https://wiki.python.org/moin/PythonEventsCalendar#Submitting_an_Event)
    * Find events from the Python Community around the world!


  * [>_ Launch Interactive Shell ](https://www.python.org/shell/)


  * ```
# Python 3: Fibonacci series up to n
>>> def fib(n):
>>>     a, b = 0, 1
>>>     while a < n:
>>>         print(a, end=' ')
>>>         a, b = b, a+b
>>>     print()
>>> fib(1000)
0 1 1 2 3 5 8 13 21 34 55 89 144 233 377 610 987
```

# Functions Defined
The core of extensible programming is defining functions. Python allows mandatory and optional arguments, keyword arguments, and even arbitrary argument lists. [More about defining functions in Python 3](https://docs.python.org/3/tutorial/controlflow.html#defining-functions)
  * ```
# Python 3: List comprehensions
>>> fruits = ['Banana', 'Apple', 'Lime']
>>> loud_fruits = [fruit.upper() for fruit in fruits]
>>> print(loud_fruits)
['BANANA', 'APPLE', 'LIME']

# List and the enumerate function
>>> list(enumerate(fruits))
[(0, 'Banana'), (1, 'Apple'), (2, 'Lime')]
```

# Compound Data Types
Lists (known as arrays in other languages) are one of the compound data types that Python understands. Lists can be indexed, sliced and manipulated with other built-in functions. [More about lists in Python 3](https://docs.python.org/3/tutorial/introduction.html#lists)
  * ```
# Python 3: Simple arithmetic
>>> 1 / 2
0.5
>>> 2 ** 3
8
>>> 17 / 3  # classic division returns a float
5.666666666666667
>>> 17 // 3  # floor division
5
```

# Intuitive Interpretation
Calculations are simple with Python, and expression syntax is straightforward: the operators `+`, `-`, `*` and `/` work as expected; parentheses `()` can be used for grouping. [More about simple math functions in Python 3](http://docs.python.org/3/tutorial/introduction.html#using-python-as-a-calculator).
  * ```
# For loop on a list
>>> numbers = [2, 4, 6, 8]
>>> product = 1
>>> for number in numbers:
...    product = product * number
... 
>>> print('The product is:', product)
The product is: 384
```

# All the Flow You’d Expect
Python knows the usual control flow statements that other languages speak — `if`, `for`, `while` and `range` — with some of its own twists, of course. [More control flow tools in Python 3](https://docs.python.org/3/tutorial/controlflow.html)
  * ```
# Simple output (with Unicode)
>>> print("Hello, I'm Python!")
Hello, I'm Python!
# Input, assignment
>>> name = input('What is your name?\n')
What is your name?
Python
>>> print(f'Hi, {name}.')
Hi, Python.

```

# Quick & Easy to Learn
Experienced programmers in any other language can pick up Python very quickly, and beginners find the clean syntax and indentation structure easy to learn. [Whet your appetite](https://docs.python.org/3/tutorial/) with our Python 3 overview.


  1. 1
  2. 2
  3. 3
  4. 4
  5. 5


Python is a programming language that lets you work quickly [Learn More](https://www.python.org/doc/)
Whether you're new to programming or an experienced developer, it's easy to learn and use Python.
[Start with our Beginner’s Guide](https://www.python.org/about/gettingstarted/)
Python source code and installers are available for download for all versions!
Latest: [Python 3.14.3](https://www.python.org/downloads/release/python-3143/)
Documentation for Python's standard library, along with tutorials and guides, are available online.
[docs.python.org](https://docs.python.org)
Looking for work or have a Python related position that you're trying to hire for? Our **relaunched community-run job board** is the place to go.
[jobs.python.org](https://jobs.python.org)
[More](https://blog.python.org "More News")
  * 2026-02-03 [Python 3.14.3 and 3.13.12 are now available!](https://pythoninsider.blogspot.com/2026/02/python-3143-and-31312-are-now-available.html)
  * 2026-01-26 [Your Python. Your Voice. Join the Python Developers Survey 2026!](https://pyfound.blogspot.com/2026/01/your-python-your-voice-join-python.html)
  * 2026-01-21 [Departing the Python Software Foundation (Staff)](https://pyfound.blogspot.com/2026/01/ee-departing-the-psf-staff.html)
  * 2026-01-20 [Announcing Python Software Foundation Fellow Members for Q4 2025! 🎉](https://pyfound.blogspot.com/2026/01/announcing-python-software-foundation.html)
  * 2026-01-14 [Python 3.15.0 alpha 5 (yes, another alpha!)](https://pythoninsider.blogspot.com/2026/01/python-3150-alpha-5-yes-another-alpha.html)


[More](https://www.python.org/events/calendars/ "More Events")
  * 2026-02-20 [PyCon Namibia 2026](https://www.python.org/events/python-events/2121/)
  * 2026-02-21 [PyCon mini Shizuoka 2026](https://www.python.org/events/python-user-group/2144/)
  * 2026-02-21 [Python BarCamp Karlsruhe 2026](https://www.python.org/events/python-user-group/2140/)
  * 2026-03-14 [PyConf Hyderabad 2026](https://www.python.org/events/python-events/2128/)
  * 2026-03-21 [PythonAsia 2026](https://www.python.org/events/python-events/2135/)


[More](https://www.python.org/success-stories/ "More Success Stories")
> [Since its founding in 2007, Lincoln Loop has been building sites for their clients with Python and Django. They credit Python's philosophy of practicality and explicitness, along with the rich ecosystem of open-source libraries available on PyPI, as keys to their success. Additionally, the inclusivity, openness, and strong culture of collaboration in the Python community have enabled the agency to find and hire great people who are lifelong learners.](https://www.python.org/success-stories/lincoln-loop-building-a-sustainable-business-inspired-by-pythons-ethos/)
[Lincoln Loop: Building a sustainable business inspired by Python’s ethos](https://www.python.org/success-stories/lincoln-loop-building-a-sustainable-business-inspired-by-pythons-ethos/) _by Peter Baumgartner_  
---  
[More](https://www.python.org/about/apps "More Applications")
  * **Web Development** : [Django](https://www.djangoproject.com/), [Pyramid](https://trypyramid.com/), [Bottle](https://bottlepy.org), [Tornado](https://www.tornadoweb.org/), [Flask](https://flask.palletsprojects.com/), [Litestar](https://litestar.dev/), [web2py](https://www.web2py.com/)
  * **GUI Development** : [tkInter](https://wiki.python.org/moin/TkInter), [PyGObject](https://wiki.gnome.org/Projects/PyGObject), [PyQt](https://riverbankcomputing.com/software/pyqt/intro), [PySide](https://wiki.qt.io/Qt_for_Python), [Kivy](https://kivy.org/), [wxPython](https://www.wxpython.org/), [DearPyGui](https://dearpygui.readthedocs.io/en/latest/)
  * **Scientific and Numeric** :  [SciPy](https://scipy.org/), [Pandas](https://pandas.pydata.org/), [IPython](https://ipython.org/)
  * **Software Development** : [Buildbot](https://buildbot.net/), [Trac](https://trac.edgewall.org/), [Roundup](https://www.roundup-tracker.org/)
  * **System Administration** : [Ansible](https://docs.ansible.com/), [Salt](https://saltproject.io/), [OpenStack](https://www.openstack.org/), [xonsh](https://xon.sh/)


##  >>> [Python Software Foundation](https://www.python.org/psf/)
The mission of the Python Software Foundation is to promote, protect, and advance the Python programming language, and to support and facilitate the growth of a diverse and international community of Python programmers. [Learn more](https://www.python.org/psf/)
[Become a Member](https://www.python.org/psf/membership/) [Donate to the PSF](https://www.python.org/psf/donations/)
[▲ Back to Top](https://www.python.org/#python-network)
  * [About](https://www.python.org/about/)
    * [Applications](https://www.python.org/about/apps/)
    * [Quotes](https://www.python.org/about/quotes/)
    * [Getting Started](https://www.python.org/about/gettingstarted/)
    * [Help](https://www.python.org/about/help/)
    * [Python Brochure](http://brochure.getpython.info/)
  * [Downloads](https://www.python.org/downloads/)
    * [All releases](https://www.python.org/downloads/)
    * [Source code](https://www.python.org/downloads/source/)
    * [Windows](https://www.python.org/downloads/windows/)
    * [macOS](https://www.python.org/downloads/macos/)
    * [Android](https://www.python.org/downloads/android/)
    * [Other Platforms](https://www.python.org/download/other/)
    * [License](https://docs.python.org/3/license.html)
    * [Alternative Implementations](https://www.python.org/download/alternatives)
  * [Documentation](https://www.python.org/doc/)
    * [Docs](https://www.python.org/doc/)
    * [Audio/Visual Talks](https://www.python.org/doc/av)
    * [Beginner's Guide](https://wiki.python.org/moin/BeginnersGuide)
    * [FAQ](https://docs.python.org/3/faq/)
    * [Non-English Docs](https://translations.python.org/)
    * [PEP Index](https://peps.python.org)
    * [Python Books](https://wiki.python.org/moin/PythonBooks)
    * [Python Essays](https://www.python.org/doc/essays/)
  * [Community](https://www.python.org/community/)
    * [Diversity](https://www.python.org/community/diversity/)
    * [Mailing Lists](https://www.python.org/community/lists/)
    * [IRC](https://www.python.org/community/irc/)
    * [Forums](https://www.python.org/community/forums/)
    * [PSF Annual Impact Report](https://www.python.org/psf/annual-report/2024/)
    * [Python Conferences](https://www.python.org/community/workshops/)
    * [Special Interest Groups](https://www.python.org/community/sigs/)
    * [Python Logo](https://www.python.org/community/logos/)
    * [Python Wiki](https://wiki.python.org/moin/)
    * [Code of Conduct](https://www.python.org/psf/conduct/)
    * [Community Awards](https://www.python.org/community/awards)
    * [Get Involved](https://www.python.org/psf/get-involved/)
    * [Shared Stories](https://www.python.org/psf/community-stories/)
  * [Success Stories](https://www.python.org/success-stories/ "success-stories")
    * [Arts](https://www.python.org/success-stories/category/arts/)
    * [Business](https://www.python.org/success-stories/category/business/)
    * [Education](https://www.python.org/success-stories/category/education/)
    * [Engineering](https://www.python.org/success-stories/category/engineering/)
    * [Government](https://www.python.org/success-stories/category/government/)
    * [Scientific](https://www.python.org/success-stories/category/scientific/)
    * [Software Development](https://www.python.org/success-stories/category/software-development/)
  * [News](https://www.python.org/blogs/ "News from around the Python world")
    * [Python News](https://www.python.org/blogs/ "Python Insider Blog Posts")
    * [PSF Newsletter](https://www.python.org/psf/newsletter/ "Python Software Foundation Newsletter")
    * [PSF News](http://pyfound.blogspot.com/ "PSF Blog")
    * [PyCon US News](http://pycon.blogspot.com/ "PyCon Blog")
    * [News from the Community](http://planetpython.org/ "Planet Python")
  * [Events](https://www.python.org/events/)
    * [Python Events](https://www.python.org/events/python-events/)
    * [User Group Events](https://www.python.org/events/python-user-group/)
    * [Python Events Archive](https://www.python.org/events/python-events/past/)
    * [User Group Events Archive](https://www.python.org/events/python-user-group/past/)
    * [Submit an Event](https://wiki.python.org/moin/PythonEventsCalendar#Submitting_an_Event)
  * [Contributing](https://www.python.org/dev/)
    * [Developer's Guide](https://devguide.python.org/)
    * [Issue Tracker](https://github.com/python/cpython/issues)
    * [python-dev list](https://mail.python.org/mailman/listinfo/python-dev)
    * [Core Mentorship](https://www.python.org/dev/core-mentorship/)
    * [Report a Security Issue](https://www.python.org/dev/security/)

[▲ Back to Top](https://www.python.org/#python-network)
  * [Help & General Contact](https://www.python.org/about/help/)
  * [Diversity Initiatives](https://www.python.org/community/diversity/)
  * [Submit Website Bug](https://github.com/python/pythondotorg/issues)
  * [Status ](https://status.python.org/ "All Systems Operational")


Copyright ©2001-2026. [Python Software Foundation](https://www.python.org/psf-landing/) [Legal Statements](https://www.python.org/about/legal/) [Privacy Notice](https://policies.python.org/python.org/Privacy-Notice/)


---

<!-- SOURCE: https://docs.python.org/3/library/asyncio.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
#### Previous topic
[Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html "previous chapter")
#### Next topic
[Runners](https://docs.python.org/3/library/asyncio-runner.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio.rst?plain=1)


### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-runner.html "Runners") |
  * [previous](https://docs.python.org/3/library/ipc.html "Networking and Interprocess Communication") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html)
  * | 
  * Theme  Auto Light Dark |


#  `asyncio` — Asynchronous I/O[¶](https://docs.python.org/3/library/asyncio.html#module-asyncio "Link to this heading")
* * *
Hello World!
Copy```
import asyncio

async def main():
    print('Hello ...')
    await asyncio.sleep(1)
    print('... World!')

asyncio.run(main())

```

asyncio is a library to write **concurrent** code using the **async/await** syntax.
asyncio is used as a foundation for multiple Python asynchronous frameworks that provide high-performance network and web-servers, database connection libraries, distributed task queues, etc.
asyncio is often a perfect fit for IO-bound and high-level **structured** network code.
See also 

[A Conceptual Overview of asyncio](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#a-conceptual-overview-of-asyncio)
    
Explanation of the fundamentals of asyncio.
asyncio provides a set of **high-level** APIs to:
  * [run Python coroutines](https://docs.python.org/3/library/asyncio-task.html#coroutine) concurrently and have full control over their execution;
  * perform [network IO and IPC](https://docs.python.org/3/library/asyncio-stream.html#asyncio-streams);
  * control [subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio-subprocess);
  * distribute tasks via [queues](https://docs.python.org/3/library/asyncio-queue.html#asyncio-queues);
  * [synchronize](https://docs.python.org/3/library/asyncio-sync.html#asyncio-sync) concurrent code;


Additionally, there are **low-level** APIs for _library and framework developers_ to:
  * create and manage [event loops](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio-event-loop), which provide asynchronous APIs for [networking](https://docs.python.org/3/library/asyncio-eventloop.html#loop-create-server), running [subprocesses](https://docs.python.org/3/library/asyncio-eventloop.html#loop-subprocess-exec), handling [OS signals](https://docs.python.org/3/library/asyncio-eventloop.html#loop-add-signal-handler), etc;
  * implement efficient protocols using [transports](https://docs.python.org/3/library/asyncio-protocol.html#asyncio-transports-protocols);
  * [bridge](https://docs.python.org/3/library/asyncio-future.html#asyncio-futures) callback-based libraries and code with async/await syntax.


[Availability](https://docs.python.org/3/library/intro.html#availability): not WASI.
This module does not work or is not available on WebAssembly. See [WebAssembly platforms](https://docs.python.org/3/library/intro.html#wasm-availability) for more information.
asyncio REPL
You can experiment with an `asyncio` concurrent context in the [REPL](https://docs.python.org/3/glossary.html#term-REPL):
Copy```
$ python -m asyncio
asyncio REPL ...
Use "await" directly instead of "asyncio.run()".
Type "help", "copyright", "credits" or "license" for more information.
>>> import asyncio
>>> await asyncio.sleep(10, result='hello')
'hello'

```

This REPL provides limited compatibility with [`PYTHON_BASIC_REPL`](https://docs.python.org/3/using/cmdline.html#envvar-PYTHON_BASIC_REPL). It is recommended that the default REPL is used for full functionality and the latest features.
Raises an [auditing event](https://docs.python.org/3/library/sys.html#auditing) `cpython.run_stdin` with no arguments.
Changed in version 3.12.5: (also 3.11.10, 3.10.15, 3.9.20, and 3.8.20) Emits audit events.
Changed in version 3.13: Uses PyREPL if possible, in which case [`PYTHONSTARTUP`](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONSTARTUP) is also executed. Emits audit events.
Reference
High-level APIs
  * [Runners](https://docs.python.org/3/library/asyncio-runner.html)
  * [Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html)
  * [Streams](https://docs.python.org/3/library/asyncio-stream.html)
  * [Synchronization Primitives](https://docs.python.org/3/library/asyncio-sync.html)
  * [Subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html)
  * [Queues](https://docs.python.org/3/library/asyncio-queue.html)
  * [Exceptions](https://docs.python.org/3/library/asyncio-exceptions.html)
  * [Call Graph Introspection](https://docs.python.org/3/library/asyncio-graph.html)


Low-level APIs
  * [Event Loop](https://docs.python.org/3/library/asyncio-eventloop.html)
  * [Futures](https://docs.python.org/3/library/asyncio-future.html)
  * [Transports and Protocols](https://docs.python.org/3/library/asyncio-protocol.html)
  * [Policies](https://docs.python.org/3/library/asyncio-policy.html)
  * [Platform Support](https://docs.python.org/3/library/asyncio-platforms.html)
  * [Extending](https://docs.python.org/3/library/asyncio-extending.html)


Guides and Tutorials
  * [High-level API Index](https://docs.python.org/3/library/asyncio-api-index.html)
  * [Low-level API Index](https://docs.python.org/3/library/asyncio-llapi-index.html)
  * [Developing with asyncio](https://docs.python.org/3/library/asyncio-dev.html)


Note
The source code for asyncio can be found in [Lib/asyncio/](https://github.com/python/cpython/tree/3.14/Lib/asyncio/).
#### Previous topic
[Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html "previous chapter")
#### Next topic
[Runners](https://docs.python.org/3/library/asyncio-runner.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio.rst?plain=1)


«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-runner.html "Runners") |
  * [previous](https://docs.python.org/3/library/ipc.html "Networking and Interprocess Communication") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 


---

<!-- SOURCE: https://docs.python.org/3/library/ipc.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
#### Previous topic
[`_thread` — Low-level threading API](https://docs.python.org/3/library/_thread.html "previous chapter")
#### Next topic
[`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/ipc.rst?plain=1)


### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio.html "asyncio — Asynchronous I/O") |
  * [previous](https://docs.python.org/3/library/_thread.html "_thread — Low-level threading API") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html)
  * | 
  * Theme  Auto Light Dark |


# Networking and Interprocess Communication[¶](https://docs.python.org/3/library/ipc.html#networking-and-interprocess-communication "Link to this heading")
The modules described in this chapter provide mechanisms for networking and inter-processes communication.
Some modules only work for two processes that are on the same machine, e.g. [`signal`](https://docs.python.org/3/library/signal.html#module-signal "signal: Set handlers for asynchronous events.") and [`mmap`](https://docs.python.org/3/library/mmap.html#module-mmap "mmap: Interface to memory-mapped files for Unix and Windows."). Other modules support networking protocols that two or more processes can use to communicate across machines.
The list of modules described in this chapter is:
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html)
  * [`socket` — Low-level networking interface](https://docs.python.org/3/library/socket.html)
  * [`ssl` — TLS/SSL wrapper for socket objects](https://docs.python.org/3/library/ssl.html)
  * [`select` — Waiting for I/O completion](https://docs.python.org/3/library/select.html)
  * [`selectors` — High-level I/O multiplexing](https://docs.python.org/3/library/selectors.html)
  * [`signal` — Set handlers for asynchronous events](https://docs.python.org/3/library/signal.html)
  * [`mmap` — Memory-mapped file support](https://docs.python.org/3/library/mmap.html)


#### Previous topic
[`_thread` — Low-level threading API](https://docs.python.org/3/library/_thread.html "previous chapter")
#### Next topic
[`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/ipc.rst?plain=1)


«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio.html "asyncio — Asynchronous I/O") |
  * [previous](https://docs.python.org/3/library/_thread.html "_thread — Low-level threading API") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 


---

<!-- SOURCE: https://docs.python.org/3/library/asyncio-subprocess.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
### [Table of Contents](https://docs.python.org/3/contents.html)
  * [Subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html)
    * [Creating Subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html#creating-subprocesses)
    * [Constants](https://docs.python.org/3/library/asyncio-subprocess.html#constants)
    * [Interacting with Subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html#interacting-with-subprocesses)
      * [Subprocess and Threads](https://docs.python.org/3/library/asyncio-subprocess.html#subprocess-and-threads)
      * [Examples](https://docs.python.org/3/library/asyncio-subprocess.html#examples)


#### Previous topic
[Synchronization Primitives](https://docs.python.org/3/library/asyncio-sync.html "previous chapter")
#### Next topic
[Queues](https://docs.python.org/3/library/asyncio-queue.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio-subprocess.rst?plain=1)


### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-queue.html "Queues") |
  * [previous](https://docs.python.org/3/library/asyncio-sync.html "Synchronization Primitives") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html) »
  * [Subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html)
  * | 
  * Theme  Auto Light Dark |


# Subprocesses[¶](https://docs.python.org/3/library/asyncio-subprocess.html#subprocesses "Link to this heading")
**Source code:** [Lib/asyncio/subprocess.py](https://github.com/python/cpython/tree/3.14/Lib/asyncio/subprocess.py), [Lib/asyncio/base_subprocess.py](https://github.com/python/cpython/tree/3.14/Lib/asyncio/base_subprocess.py)
* * *
This section describes high-level async/await asyncio APIs to create and manage subprocesses.
Here’s an example of how asyncio can run a shell command and obtain its result:
Copy```
import asyncio

async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if stdout:
        print(f'[stdout]\n{stdout.decode()}')
    if stderr:
        print(f'[stderr]\n{stderr.decode()}')

asyncio.run(run('ls /zzz'))

```

will print:
Copy```
['ls /zzz' exited with 1]
[stderr]
ls: /zzz: No such file or directory

```

Because all asyncio subprocess functions are asynchronous and asyncio provides many tools to work with such functions, it is easy to execute and monitor multiple subprocesses in parallel. It is indeed trivial to modify the above example to run several commands simultaneously:
Copy```
async def main():
    await asyncio.gather(
        run('ls /zzz'),
        run('sleep 1; echo "hello"'))

asyncio.run(main())

```

See also the [Examples](https://docs.python.org/3/library/asyncio-subprocess.html#examples) subsection.
## Creating Subprocesses[¶](https://docs.python.org/3/library/asyncio-subprocess.html#creating-subprocesses "Link to this heading") 

_async_ asyncio.create_subprocess_exec(_program_ , _* args_, _stdin =None_, _stdout =None_, _stderr =None_, _limit =None_, _** kwds_)[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_exec "Link to this definition") 
    
Create a subprocess.
The _limit_ argument sets the buffer limit for [`StreamReader`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader "asyncio.StreamReader") wrappers for [`stdout`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stdout "asyncio.subprocess.Process.stdout") and [`stderr`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stderr "asyncio.subprocess.Process.stderr") (if [`subprocess.PIPE`](https://docs.python.org/3/library/subprocess.html#subprocess.PIPE "subprocess.PIPE") is passed to _stdout_ and _stderr_ arguments).
Return a [`Process`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process "asyncio.subprocess.Process") instance.
See the documentation of [`loop.subprocess_exec()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.subprocess_exec "asyncio.loop.subprocess_exec") for other parameters.
If the process object is garbage collected while the process is still running, the child process will be killed.
Changed in version 3.10: Removed the _loop_ parameter. 

_async_ asyncio.create_subprocess_shell(_cmd_ , _stdin =None_, _stdout =None_, _stderr =None_, _limit =None_, _** kwds_)[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_shell "Link to this definition") 
    
Run the _cmd_ shell command.
The _limit_ argument sets the buffer limit for [`StreamReader`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader "asyncio.StreamReader") wrappers for [`stdout`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stdout "asyncio.subprocess.Process.stdout") and [`stderr`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stderr "asyncio.subprocess.Process.stderr") (if [`subprocess.PIPE`](https://docs.python.org/3/library/subprocess.html#subprocess.PIPE "subprocess.PIPE") is passed to _stdout_ and _stderr_ arguments).
Return a [`Process`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process "asyncio.subprocess.Process") instance.
See the documentation of [`loop.subprocess_shell()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.subprocess_shell "asyncio.loop.subprocess_shell") for other parameters.
If the process object is garbage collected while the process is still running, the child process will be killed.
Important
It is the application’s responsibility to ensure that all whitespace and special characters are quoted appropriately to avoid [shell injection](https://en.wikipedia.org/wiki/Shell_injection#Shell_injection) vulnerabilities. The [`shlex.quote()`](https://docs.python.org/3/library/shlex.html#shlex.quote "shlex.quote") function can be used to properly escape whitespace and special shell characters in strings that are going to be used to construct shell commands.
Changed in version 3.10: Removed the _loop_ parameter.
Note
Subprocesses are available for Windows if a [`ProactorEventLoop`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.ProactorEventLoop "asyncio.ProactorEventLoop") is used. See [Subprocess Support on Windows](https://docs.python.org/3/library/asyncio-platforms.html#asyncio-windows-subprocess) for details.
See also
asyncio also has the following _low-level_ APIs to work with subprocesses: [`loop.subprocess_exec()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.subprocess_exec "asyncio.loop.subprocess_exec"), [`loop.subprocess_shell()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.subprocess_shell "asyncio.loop.subprocess_shell"), [`loop.connect_read_pipe()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.connect_read_pipe "asyncio.loop.connect_read_pipe"), [`loop.connect_write_pipe()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.connect_write_pipe "asyncio.loop.connect_write_pipe"), as well as the [Subprocess Transports](https://docs.python.org/3/library/asyncio-protocol.html#asyncio-subprocess-transports) and [Subprocess Protocols](https://docs.python.org/3/library/asyncio-protocol.html#asyncio-subprocess-protocols).
## Constants[¶](https://docs.python.org/3/library/asyncio-subprocess.html#constants "Link to this heading") 

asyncio.subprocess.PIPE[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.PIPE "Link to this definition") 
    
Can be passed to the _stdin_ , _stdout_ or _stderr_ parameters.
If _PIPE_ is passed to _stdin_ argument, the [`Process.stdin`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stdin "asyncio.subprocess.Process.stdin") attribute will point to a [`StreamWriter`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter "asyncio.StreamWriter") instance.
If _PIPE_ is passed to _stdout_ or _stderr_ arguments, the [`Process.stdout`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stdout "asyncio.subprocess.Process.stdout") and [`Process.stderr`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stderr "asyncio.subprocess.Process.stderr") attributes will point to [`StreamReader`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader "asyncio.StreamReader") instances. 

asyncio.subprocess.STDOUT[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.STDOUT "Link to this definition") 
    
Special value that can be used as the _stderr_ argument and indicates that standard error should be redirected into standard output. 

asyncio.subprocess.DEVNULL[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.DEVNULL "Link to this definition") 
    
Special value that can be used as the _stdin_ , _stdout_ or _stderr_ argument to process creation functions. It indicates that the special file [`os.devnull`](https://docs.python.org/3/library/os.html#os.devnull "os.devnull") will be used for the corresponding subprocess stream.
## Interacting with Subprocesses[¶](https://docs.python.org/3/library/asyncio-subprocess.html#interacting-with-subprocesses "Link to this heading")
Both [`create_subprocess_exec()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_exec "asyncio.create_subprocess_exec") and [`create_subprocess_shell()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_shell "asyncio.create_subprocess_shell") functions return instances of the _Process_ class. _Process_ is a high-level wrapper that allows communicating with subprocesses and watching for their completion. 

_class_ asyncio.subprocess.Process[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process "Link to this definition") 
    
An object that wraps OS processes created by the [`create_subprocess_exec()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_exec "asyncio.create_subprocess_exec") and [`create_subprocess_shell()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_shell "asyncio.create_subprocess_shell") functions.
This class is designed to have a similar API to the [`subprocess.Popen`](https://docs.python.org/3/library/subprocess.html#subprocess.Popen "subprocess.Popen") class, but there are some notable differences:
  * unlike Popen, Process instances do not have an equivalent to the [`poll()`](https://docs.python.org/3/library/subprocess.html#subprocess.Popen.poll "subprocess.Popen.poll") method;
  * the [`communicate()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.communicate "asyncio.subprocess.Process.communicate") and [`wait()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.wait "asyncio.subprocess.Process.wait") methods don’t have a _timeout_ parameter: use the [`wait_for()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for "asyncio.wait_for") function;
  * the [`Process.wait()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.wait "asyncio.subprocess.Process.wait") method is asynchronous, whereas [`subprocess.Popen.wait()`](https://docs.python.org/3/library/subprocess.html#subprocess.Popen.wait "subprocess.Popen.wait") method is implemented as a blocking busy loop;
  * the _universal_newlines_ parameter is not supported.


This class is [not thread safe](https://docs.python.org/3/library/asyncio-dev.html#asyncio-multithreading).
See also the [Subprocess and Threads](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio-subprocess-threads) section. 

_async_ wait()[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.wait "Link to this definition") 
    
Wait for the child process to terminate.
Set and return the [`returncode`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.returncode "asyncio.subprocess.Process.returncode") attribute.
Note
This method can deadlock when using `stdout=PIPE` or `stderr=PIPE` and the child process generates so much output that it blocks waiting for the OS pipe buffer to accept more data. Use the [`communicate()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.communicate "asyncio.subprocess.Process.communicate") method when using pipes to avoid this condition. 

_async_ communicate(_input =None_)[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.communicate "Link to this definition") 
    
Interact with process:
  1. send data to _stdin_ (if _input_ is not `None`);
  2. closes _stdin_ ;
  3. read data from _stdout_ and _stderr_ , until EOF is reached;
  4. wait for process to terminate.


The optional _input_ argument is the data ([`bytes`](https://docs.python.org/3/library/stdtypes.html#bytes "bytes") object) that will be sent to the child process.
Return a tuple `(stdout_data, stderr_data)`.
If either [`BrokenPipeError`](https://docs.python.org/3/library/exceptions.html#BrokenPipeError "BrokenPipeError") or [`ConnectionResetError`](https://docs.python.org/3/library/exceptions.html#ConnectionResetError "ConnectionResetError") exception is raised when writing _input_ into _stdin_ , the exception is ignored. This condition occurs when the process exits before all data are written into _stdin_.
If it is desired to send data to the process’ _stdin_ , the process needs to be created with `stdin=PIPE`. Similarly, to get anything other than `None` in the result tuple, the process has to be created with `stdout=PIPE` and/or `stderr=PIPE` arguments.
Note, that the data read is buffered in memory, so do not use this method if the data size is large or unlimited.
Changed in version 3.12: _stdin_ gets closed when `input=None` too. 

send_signal(_signal_)[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.send_signal "Link to this definition") 
    
Sends the signal _signal_ to the child process.
Note
On Windows, [`SIGTERM`](https://docs.python.org/3/library/signal.html#signal.SIGTERM "signal.SIGTERM") is an alias for [`terminate()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.terminate "asyncio.subprocess.Process.terminate"). `CTRL_C_EVENT` and `CTRL_BREAK_EVENT` can be sent to processes started with a _creationflags_ parameter which includes `CREATE_NEW_PROCESS_GROUP`. 

terminate()[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.terminate "Link to this definition") 
    
Stop the child process.
On POSIX systems this method sends [`SIGTERM`](https://docs.python.org/3/library/signal.html#signal.SIGTERM "signal.SIGTERM") to the child process.
On Windows the Win32 API function `TerminateProcess()` is called to stop the child process. 

kill()[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.kill "Link to this definition") 
    
Kill the child process.
On POSIX systems this method sends [`SIGKILL`](https://docs.python.org/3/library/signal.html#signal.SIGKILL "signal.SIGKILL") to the child process.
On Windows this method is an alias for [`terminate()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.terminate "asyncio.subprocess.Process.terminate"). 

stdin[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stdin "Link to this definition") 
    
Standard input stream ([`StreamWriter`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter "asyncio.StreamWriter")) or `None` if the process was created with `stdin=None`. 

stdout[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stdout "Link to this definition") 
    
Standard output stream ([`StreamReader`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader "asyncio.StreamReader")) or `None` if the process was created with `stdout=None`. 

stderr[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stderr "Link to this definition") 
    
Standard error stream ([`StreamReader`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader "asyncio.StreamReader")) or `None` if the process was created with `stderr=None`.
Warning
Use the [`communicate()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.communicate "asyncio.subprocess.Process.communicate") method rather than [`process.stdin.write()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stdin "asyncio.subprocess.Process.stdin"), [`await process.stdout.read()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stdout "asyncio.subprocess.Process.stdout") or [`await process.stderr.read()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stderr "asyncio.subprocess.Process.stderr"). This avoids deadlocks due to streams pausing reading or writing and blocking the child process. 

pid[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.pid "Link to this definition") 
    
Process identification number (PID).
Note that for processes created by the [`create_subprocess_shell()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_shell "asyncio.create_subprocess_shell") function, this attribute is the PID of the spawned shell. 

returncode[¶](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.returncode "Link to this definition") 
    
Return code of the process when it exits.
A `None` value indicates that the process has not terminated yet.
A negative value `-N` indicates that the child was terminated by signal `N` (POSIX only).
### Subprocess and Threads[¶](https://docs.python.org/3/library/asyncio-subprocess.html#subprocess-and-threads "Link to this heading")
Standard asyncio event loop supports running subprocesses from different threads by default.
On Windows subprocesses are provided by [`ProactorEventLoop`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.ProactorEventLoop "asyncio.ProactorEventLoop") only (default), [`SelectorEventLoop`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.SelectorEventLoop "asyncio.SelectorEventLoop") has no subprocess support.
Note that alternative event loop implementations might have own limitations; please refer to their documentation.
See also
The [Concurrency and multithreading in asyncio](https://docs.python.org/3/library/asyncio-dev.html#asyncio-multithreading) section.
### Examples[¶](https://docs.python.org/3/library/asyncio-subprocess.html#examples "Link to this heading")
An example using the [`Process`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process "asyncio.subprocess.Process") class to control a subprocess and the [`StreamReader`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader "asyncio.StreamReader") class to read from its standard output.
The subprocess is created by the [`create_subprocess_exec()`](https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_exec "asyncio.create_subprocess_exec") function:
Copy```
import asyncio
import sys

async def get_date():
    code = 'import datetime; print(datetime.datetime.now())'

    # Create the subprocess; redirect the standard output
    # into a pipe.
    proc = await asyncio.create_subprocess_exec(
        sys.executable, '-c', code,
        stdout=asyncio.subprocess.PIPE)

    # Read one line of output.
    data = await proc.stdout.readline()
    line = data.decode('ascii').rstrip()

    # Wait for the subprocess exit.
    await proc.wait()
    return line

date = asyncio.run(get_date())
print(f"Current date: {date}")

```

See also the [same example](https://docs.python.org/3/library/asyncio-protocol.html#asyncio-example-subprocess-proto) written using low-level APIs.
### [Table of Contents](https://docs.python.org/3/contents.html)
  * [Subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html)
    * [Creating Subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html#creating-subprocesses)
    * [Constants](https://docs.python.org/3/library/asyncio-subprocess.html#constants)
    * [Interacting with Subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html#interacting-with-subprocesses)
      * [Subprocess and Threads](https://docs.python.org/3/library/asyncio-subprocess.html#subprocess-and-threads)
      * [Examples](https://docs.python.org/3/library/asyncio-subprocess.html#examples)


#### Previous topic
[Synchronization Primitives](https://docs.python.org/3/library/asyncio-sync.html "previous chapter")
#### Next topic
[Queues](https://docs.python.org/3/library/asyncio-queue.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio-subprocess.rst?plain=1)


«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-queue.html "Queues") |
  * [previous](https://docs.python.org/3/library/asyncio-sync.html "Synchronization Primitives") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html) »
  * [Subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 


---

<!-- SOURCE: https://docs.python.org/3/library/asyncio-queue.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
### [Table of Contents](https://docs.python.org/3/contents.html)
  * [Queues](https://docs.python.org/3/library/asyncio-queue.html)
    * [Queue](https://docs.python.org/3/library/asyncio-queue.html#queue)
    * [Priority Queue](https://docs.python.org/3/library/asyncio-queue.html#priority-queue)
    * [LIFO Queue](https://docs.python.org/3/library/asyncio-queue.html#lifo-queue)
    * [Exceptions](https://docs.python.org/3/library/asyncio-queue.html#exceptions)
    * [Examples](https://docs.python.org/3/library/asyncio-queue.html#examples)


#### Previous topic
[Subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html "previous chapter")
#### Next topic
[Exceptions](https://docs.python.org/3/library/asyncio-exceptions.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio-queue.rst?plain=1)


### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-exceptions.html "Exceptions") |
  * [previous](https://docs.python.org/3/library/asyncio-subprocess.html "Subprocesses") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html) »
  * [Queues](https://docs.python.org/3/library/asyncio-queue.html)
  * | 
  * Theme  Auto Light Dark |


# Queues[¶](https://docs.python.org/3/library/asyncio-queue.html#queues "Link to this heading")
**Source code:** [Lib/asyncio/queues.py](https://github.com/python/cpython/tree/3.14/Lib/asyncio/queues.py)
* * *
asyncio queues are designed to be similar to classes of the [`queue`](https://docs.python.org/3/library/queue.html#module-queue "queue: A synchronized queue class.") module. Although asyncio queues are not thread-safe, they are designed to be used specifically in async/await code.
Note that methods of asyncio queues don’t have a _timeout_ parameter; use [`asyncio.wait_for()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for "asyncio.wait_for") function to do queue operations with a timeout.
See also the [Examples](https://docs.python.org/3/library/asyncio-queue.html#examples) section below.
## Queue[¶](https://docs.python.org/3/library/asyncio-queue.html#queue "Link to this heading") 

_class_ asyncio.Queue(_maxsize =0_)[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue "Link to this definition") 
    
A first in, first out (FIFO) queue.
If _maxsize_ is less than or equal to zero, the queue size is infinite. If it is an integer greater than `0`, then `await put()` blocks when the queue reaches _maxsize_ until an item is removed by [`get()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get "asyncio.Queue.get").
Unlike the standard library threading [`queue`](https://docs.python.org/3/library/queue.html#module-queue "queue: A synchronized queue class."), the size of the queue is always known and can be returned by calling the [`qsize()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.qsize "asyncio.Queue.qsize") method.
Changed in version 3.10: Removed the _loop_ parameter.
This class is [not thread safe](https://docs.python.org/3/library/asyncio-dev.html#asyncio-multithreading). 

maxsize[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.maxsize "Link to this definition") 
    
Number of items allowed in the queue. 

empty()[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.empty "Link to this definition") 
    
Return `True` if the queue is empty, `False` otherwise. 

full()[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.full "Link to this definition") 
    
Return `True` if there are [`maxsize`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.maxsize "asyncio.Queue.maxsize") items in the queue.
If the queue was initialized with `maxsize=0` (the default), then [`full()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.full "asyncio.Queue.full") never returns `True`. 

_async_ get()[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get "Link to this definition") 
    
Remove and return an item from the queue. If queue is empty, wait until an item is available.
Raises [`QueueShutDown`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueShutDown "asyncio.QueueShutDown") if the queue has been shut down and is empty, or if the queue has been shut down immediately. 

get_nowait()[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get_nowait "Link to this definition") 
    
Return an item if one is immediately available, else raise [`QueueEmpty`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueEmpty "asyncio.QueueEmpty"). 

_async_ join()[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.join "Link to this definition") 
    
Block until all items in the queue have been received and processed.
The count of unfinished tasks goes up whenever an item is added to the queue. The count goes down whenever a consumer coroutine calls [`task_done()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.task_done "asyncio.Queue.task_done") to indicate that the item was retrieved and all work on it is complete. When the count of unfinished tasks drops to zero, [`join()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.join "asyncio.Queue.join") unblocks. 

_async_ put(_item_)[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put "Link to this definition") 
    
Put an item into the queue. If the queue is full, wait until a free slot is available before adding the item.
Raises [`QueueShutDown`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueShutDown "asyncio.QueueShutDown") if the queue has been shut down. 

put_nowait(_item_)[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put_nowait "Link to this definition") 
    
Put an item into the queue without blocking.
If no free slot is immediately available, raise [`QueueFull`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueFull "asyncio.QueueFull"). 

qsize()[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.qsize "Link to this definition") 
    
Return the number of items in the queue. 

shutdown(_immediate =False_)[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.shutdown "Link to this definition") 
    
Put a [`Queue`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue "asyncio.Queue") instance into a shutdown mode.
The queue can no longer grow. Future calls to [`put()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put "asyncio.Queue.put") raise [`QueueShutDown`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueShutDown "asyncio.QueueShutDown"). Currently blocked callers of [`put()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put "asyncio.Queue.put") will be unblocked and will raise [`QueueShutDown`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueShutDown "asyncio.QueueShutDown") in the formerly awaiting task.
If _immediate_ is false (the default), the queue can be wound down normally with [`get()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get "asyncio.Queue.get") calls to extract tasks that have already been loaded.
And if [`task_done()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.task_done "asyncio.Queue.task_done") is called for each remaining task, a pending [`join()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.join "asyncio.Queue.join") will be unblocked normally.
Once the queue is empty, future calls to [`get()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get "asyncio.Queue.get") will raise [`QueueShutDown`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueShutDown "asyncio.QueueShutDown").
If _immediate_ is true, the queue is terminated immediately. The queue is drained to be completely empty and the count of unfinished tasks is reduced by the number of tasks drained. If unfinished tasks is zero, callers of [`join()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.join "asyncio.Queue.join") are unblocked. Also, blocked callers of [`get()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get "asyncio.Queue.get") are unblocked and will raise [`QueueShutDown`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueShutDown "asyncio.QueueShutDown") because the queue is empty.
Use caution when using [`join()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.join "asyncio.Queue.join") with _immediate_ set to true. This unblocks the join even when no work has been done on the tasks, violating the usual invariant for joining a queue.
Added in version 3.13. 

task_done()[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.task_done "Link to this definition") 
    
Indicate that a formerly enqueued work item is complete.
Used by queue consumers. For each [`get()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get "asyncio.Queue.get") used to fetch a work item, a subsequent call to [`task_done()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.task_done "asyncio.Queue.task_done") tells the queue that the processing on the work item is complete.
If a [`join()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.join "asyncio.Queue.join") is currently blocking, it will resume when all items have been processed (meaning that a [`task_done()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.task_done "asyncio.Queue.task_done") call was received for every item that had been [`put()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put "asyncio.Queue.put") into the queue).
Raises [`ValueError`](https://docs.python.org/3/library/exceptions.html#ValueError "ValueError") if called more times than there were items placed in the queue.
## Priority Queue[¶](https://docs.python.org/3/library/asyncio-queue.html#priority-queue "Link to this heading") 

_class_ asyncio.PriorityQueue[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.PriorityQueue "Link to this definition") 
    
A variant of [`Queue`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue "asyncio.Queue"); retrieves entries in priority order (lowest first).
Entries are typically tuples of the form `(priority_number, data)`.
## LIFO Queue[¶](https://docs.python.org/3/library/asyncio-queue.html#lifo-queue "Link to this heading") 

_class_ asyncio.LifoQueue[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.LifoQueue "Link to this definition") 
    
A variant of [`Queue`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue "asyncio.Queue") that retrieves most recently added entries first (last in, first out).
## Exceptions[¶](https://docs.python.org/3/library/asyncio-queue.html#exceptions "Link to this heading") 

_exception_ asyncio.QueueEmpty[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueEmpty "Link to this definition") 
    
This exception is raised when the [`get_nowait()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get_nowait "asyncio.Queue.get_nowait") method is called on an empty queue. 

_exception_ asyncio.QueueFull[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueFull "Link to this definition") 
    
Exception raised when the [`put_nowait()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put_nowait "asyncio.Queue.put_nowait") method is called on a queue that has reached its _maxsize_. 

_exception_ asyncio.QueueShutDown[¶](https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueShutDown "Link to this definition") 
    
Exception raised when [`put()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put "asyncio.Queue.put") or [`get()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get "asyncio.Queue.get") is called on a queue which has been shut down.
Added in version 3.13.
## Examples[¶](https://docs.python.org/3/library/asyncio-queue.html#examples "Link to this heading")
Queues can be used to distribute workload between several concurrent tasks:
Copy```
import asyncio
import random
import time


async def worker(name, queue):
    while True:
        # Get a "work item" out of the queue.
        sleep_for = await queue.get()

        # Sleep for the "sleep_for" seconds.
        await asyncio.sleep(sleep_for)

        # Notify the queue that the "work item" has been processed.
        queue.task_done()

        print(f'{name} has slept for {sleep_for:.2f} seconds')


async def main():
    # Create a queue that we will use to store our "workload".
    queue = asyncio.Queue()

    # Generate random timings and put them into the queue.
    total_sleep_time = 0
    for _ in range(20):
        sleep_for = random.uniform(0.05, 1.0)
        total_sleep_time += sleep_for
        queue.put_nowait(sleep_for)

    # Create three worker tasks to process the queue concurrently.
    tasks = []
    for i in range(3):
        task = asyncio.create_task(worker(f'worker-{i}', queue))
        tasks.append(task)

    # Wait until the queue is fully processed.
    started_at = time.monotonic()
    await queue.join()
    total_slept_for = time.monotonic() - started_at

    # Cancel our worker tasks.
    for task in tasks:
        task.cancel()
    # Wait until all worker tasks are cancelled.
    await asyncio.gather(*tasks, return_exceptions=True)

    print('====')
    print(f'3 workers slept in parallel for {total_slept_for:.2f} seconds')
    print(f'total expected sleep time: {total_sleep_time:.2f} seconds')


asyncio.run(main())

```

### [Table of Contents](https://docs.python.org/3/contents.html)
  * [Queues](https://docs.python.org/3/library/asyncio-queue.html)
    * [Queue](https://docs.python.org/3/library/asyncio-queue.html#queue)
    * [Priority Queue](https://docs.python.org/3/library/asyncio-queue.html#priority-queue)
    * [LIFO Queue](https://docs.python.org/3/library/asyncio-queue.html#lifo-queue)
    * [Exceptions](https://docs.python.org/3/library/asyncio-queue.html#exceptions)
    * [Examples](https://docs.python.org/3/library/asyncio-queue.html#examples)


#### Previous topic
[Subprocesses](https://docs.python.org/3/library/asyncio-subprocess.html "previous chapter")
#### Next topic
[Exceptions](https://docs.python.org/3/library/asyncio-exceptions.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio-queue.rst?plain=1)


«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-exceptions.html "Exceptions") |
  * [previous](https://docs.python.org/3/library/asyncio-subprocess.html "Subprocesses") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html) »
  * [Queues](https://docs.python.org/3/library/asyncio-queue.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 


---

<!-- SOURCE: https://docs.python.org/3/index.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
### Download
[Download these documents](https://docs.python.org/3/download.html)
### Docs by version
  * [Python 3.15 (in development)](https://docs.python.org/3.15/)
  * [Python 3.14 (stable)](https://docs.python.org/3.14/)
  * [Python 3.13 (stable)](https://docs.python.org/3.13/)
  * [Python 3.12 (security-fixes)](https://docs.python.org/3.12/)
  * [Python 3.11 (security-fixes)](https://docs.python.org/3.11/)
  * [Python 3.10 (security-fixes)](https://docs.python.org/3.10/)
  * [Python 3.9 (EOL)](https://docs.python.org/3.9/)
  * [Python 3.8 (EOL)](https://docs.python.org/3.8/)
  * [Python 3.7 (EOL)](https://docs.python.org/3.7/)
  * [Python 3.6 (EOL)](https://docs.python.org/3.6/)
  * [Python 3.5 (EOL)](https://docs.python.org/3.5/)
  * [Python 3.4 (EOL)](https://docs.python.org/3.4/)
  * [Python 3.3 (EOL)](https://docs.python.org/3.3/)
  * [Python 3.2 (EOL)](https://docs.python.org/3.2/)
  * [Python 3.1 (EOL)](https://docs.python.org/3.1/)
  * [Python 3.0 (EOL)](https://docs.python.org/3.0/)
  * [Python 2.7 (EOL)](https://docs.python.org/2.7/)
  * [Python 2.6 (EOL)](https://docs.python.org/2.6/)
  * [All versions](https://www.python.org/doc/versions/)


### Other resources
  * [PEP Index](https://peps.python.org/)
  * [Beginner's Guide](https://wiki.python.org/moin/BeginnersGuide)
  * [Book List](https://wiki.python.org/moin/PythonBooks)
  * [Audio/Visual Talks](https://www.python.org/doc/av/)
  * [Python Developer’s Guide](https://devguide.python.org/)


### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [](https://docs.python.org/3/index.html)
  * | 
  * Theme  Auto Light Dark |


# Python 3.14.3 documentation
Welcome! This is the official documentation for Python 3.14.3. 
**Documentation sections:**
[What's new in Python 3.14?](https://docs.python.org/3/whatsnew/3.14.html)  
Or [all "What's new" documents since Python 2.0](https://docs.python.org/3/whatsnew/index.html) [Tutorial](https://docs.python.org/3/tutorial/index.html)  
Start here: a tour of Python's syntax and features [Library reference](https://docs.python.org/3/library/index.html)  
Standard library and builtins [Language reference](https://docs.python.org/3/reference/index.html)  
Syntax and language elements [Python setup and usage](https://docs.python.org/3/using/index.html)  
How to install, configure, and use Python [Python HOWTOs](https://docs.python.org/3/howto/index.html)  
In-depth topic manuals |  [Installing Python modules](https://docs.python.org/3/installing/index.html)  
Third-party modules and PyPI.org [Distributing Python modules](https://docs.python.org/3/distributing/index.html)  
Publishing modules for use by other people [Extending and embedding](https://docs.python.org/3/extending/index.html)  
For C/C++ programmers [Python's C API](https://docs.python.org/3/c-api/index.html)  
C API reference [FAQs](https://docs.python.org/3/faq/index.html)  
Frequently asked questions (with answers!) [Deprecations](https://docs.python.org/3/deprecations/index.html)  
Deprecated functionality  
---|---  
**Indices, glossary, and search:**
[Global module index](https://docs.python.org/3/py-modindex.html)  
All modules and libraries [General index](https://docs.python.org/3/genindex.html)  
All functions, classes, and terms [Glossary](https://docs.python.org/3/glossary.html)  
Terms explained |  [Search page](https://docs.python.org/3/search.html)  
Search this documentation [Complete table of contents](https://docs.python.org/3/contents.html)  
Lists all sections and subsections  
---|---  
**Project information:**
[Reporting issues](https://docs.python.org/3/bugs.html) [Contributing to docs](https://devguide.python.org/documentation/help-documenting/) [Download the documentation](https://docs.python.org/3/download.html) |  [History and license of Python](https://docs.python.org/3/license.html) [Copyright](https://docs.python.org/3/copyright.html) [About the documentation](https://docs.python.org/3/about.html)  
---|---  
### Download
[Download these documents](https://docs.python.org/3/download.html)
### Docs by version
  * [Python 3.15 (in development)](https://docs.python.org/3.15/)
  * [Python 3.14 (stable)](https://docs.python.org/3.14/)
  * [Python 3.13 (stable)](https://docs.python.org/3.13/)
  * [Python 3.12 (security-fixes)](https://docs.python.org/3.12/)
  * [Python 3.11 (security-fixes)](https://docs.python.org/3.11/)
  * [Python 3.10 (security-fixes)](https://docs.python.org/3.10/)
  * [Python 3.9 (EOL)](https://docs.python.org/3.9/)
  * [Python 3.8 (EOL)](https://docs.python.org/3.8/)
  * [Python 3.7 (EOL)](https://docs.python.org/3.7/)
  * [Python 3.6 (EOL)](https://docs.python.org/3.6/)
  * [Python 3.5 (EOL)](https://docs.python.org/3.5/)
  * [Python 3.4 (EOL)](https://docs.python.org/3.4/)
  * [Python 3.3 (EOL)](https://docs.python.org/3.3/)
  * [Python 3.2 (EOL)](https://docs.python.org/3.2/)
  * [Python 3.1 (EOL)](https://docs.python.org/3.1/)
  * [Python 3.0 (EOL)](https://docs.python.org/3.0/)
  * [Python 2.7 (EOL)](https://docs.python.org/2.7/)
  * [Python 2.6 (EOL)](https://docs.python.org/2.6/)
  * [All versions](https://www.python.org/doc/versions/)


### Other resources
  * [PEP Index](https://peps.python.org/)
  * [Beginner's Guide](https://wiki.python.org/moin/BeginnersGuide)
  * [Book List](https://wiki.python.org/moin/PythonBooks)
  * [Audio/Visual Talks](https://www.python.org/doc/av/)
  * [Python Developer’s Guide](https://devguide.python.org/)


«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [](https://docs.python.org/3/index.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 


---

<!-- SOURCE: https://docs.python.org/3/genindex.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [Index](https://docs.python.org/3/genindex.html)
  * | 
  * Theme  Auto Light Dark |


# Index
Index pages by letter:
[**Symbols**](https://docs.python.org/3/genindex-Symbols.html) | [**_**](https://docs.python.org/3/genindex-_.html) | [**A**](https://docs.python.org/3/genindex-A.html) | [**B**](https://docs.python.org/3/genindex-B.html) | [**C**](https://docs.python.org/3/genindex-C.html) | [**D**](https://docs.python.org/3/genindex-D.html) | [**E**](https://docs.python.org/3/genindex-E.html) | [**F**](https://docs.python.org/3/genindex-F.html) | [**G**](https://docs.python.org/3/genindex-G.html) | [**H**](https://docs.python.org/3/genindex-H.html) | [**I**](https://docs.python.org/3/genindex-I.html) | [**J**](https://docs.python.org/3/genindex-J.html) | [**K**](https://docs.python.org/3/genindex-K.html) | [**L**](https://docs.python.org/3/genindex-L.html) | [**M**](https://docs.python.org/3/genindex-M.html) | [**N**](https://docs.python.org/3/genindex-N.html) | [**O**](https://docs.python.org/3/genindex-O.html) | [**P**](https://docs.python.org/3/genindex-P.html) | [**Q**](https://docs.python.org/3/genindex-Q.html) | [**R**](https://docs.python.org/3/genindex-R.html) | [**S**](https://docs.python.org/3/genindex-S.html) | [**T**](https://docs.python.org/3/genindex-T.html) | [**U**](https://docs.python.org/3/genindex-U.html) | [**V**](https://docs.python.org/3/genindex-V.html) | [**W**](https://docs.python.org/3/genindex-W.html) | [**X**](https://docs.python.org/3/genindex-X.html) | [**Y**](https://docs.python.org/3/genindex-Y.html) | [**Z**](https://docs.python.org/3/genindex-Z.html)
[**Full index on one page** (can be huge)](https://docs.python.org/3/genindex-all.html)
«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [Index](https://docs.python.org/3/genindex.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 


---

<!-- SOURCE: https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
### [Table of Contents](https://docs.python.org/3/contents.html)
  * [A Conceptual Overview of `asyncio`](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html)
    * [A conceptual overview part 1: the high-level](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#a-conceptual-overview-part-1-the-high-level)
      * [Event Loop](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#event-loop)
      * [Asynchronous functions and coroutines](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#asynchronous-functions-and-coroutines)
      * [Tasks](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#tasks)
      * [await](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#await)
    * [A conceptual overview part 2: the nuts and bolts](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#a-conceptual-overview-part-2-the-nuts-and-bolts)
      * [The inner workings of coroutines](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#the-inner-workings-of-coroutines)
      * [Futures](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#futures)
      * [A homemade asyncio.sleep](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#a-homemade-asyncio-sleep)


#### Previous topic
[Python HOWTOs](https://docs.python.org/3/howto/index.html "previous chapter")
#### Next topic
[Porting Extension Modules to Python 3](https://docs.python.org/3/howto/cporting.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/howto/a-conceptual-overview-of-asyncio.rst?plain=1)


### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/howto/cporting.html "Porting Extension Modules to Python 3") |
  * [previous](https://docs.python.org/3/howto/index.html "Python HOWTOs") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [Python HOWTOs](https://docs.python.org/3/howto/index.html) »
  * [A Conceptual Overview of `asyncio`](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html)
  * | 
  * Theme  Auto Light Dark |


# A Conceptual Overview of `asyncio`[¶](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#a-conceptual-overview-of-asyncio "Link to this heading")
This [HOWTO](https://docs.python.org/3/howto/index.html#how-tos) article seeks to help you build a sturdy mental model of how [`asyncio`](https://docs.python.org/3/library/asyncio.html#module-asyncio "asyncio: Asynchronous I/O.") fundamentally works, helping you understand the how and why behind the recommended patterns.
You might be curious about some key `asyncio` concepts. By the end of this article, you’ll be able to comfortably answer these questions:
  * What’s happening behind the scenes when an object is awaited?
  * How does `asyncio` differentiate between a task which doesn’t need CPU time (such as a network request or file read) as opposed to a task that does (such as computing n-factorial)?
  * How to write an asynchronous variant of an operation, such as an async sleep or database request.


See also
  * The [guide](https://github.com/anordin95/a-conceptual-overview-of-asyncio/tree/main) that inspired this HOWTO article, by Alexander Nordin.
  * This in-depth [YouTube tutorial series](https://www.youtube.com/watch?v=Xbl7XjFYsN4&list=PLhNSoGM2ik6SIkVGXWBwerucXjgP1rHmB) on `asyncio` created by Python core team member, Łukasz Langa.
  * [500 Lines or Less: A Web Crawler With asyncio Coroutines](https://aosabook.org/en/500L/a-web-crawler-with-asyncio-coroutines.html) by A. Jesse Jiryu Davis and Guido van Rossum.


## A conceptual overview part 1: the high-level[¶](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#a-conceptual-overview-part-1-the-high-level "Link to this heading")
In part 1, we’ll cover the main, high-level building blocks of `asyncio`: the event loop, coroutine functions, coroutine objects, tasks, and `await`.
### Event Loop[¶](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#event-loop "Link to this heading")
Everything in `asyncio` happens relative to the event loop. It’s the star of the show. It’s like an orchestra conductor. It’s behind the scenes managing resources. Some power is explicitly granted to it, but a lot of its ability to get things done comes from the respect and cooperation of its worker bees.
In more technical terms, the event loop contains a collection of jobs to be run. Some jobs are added directly by you, and some indirectly by `asyncio`. The event loop takes a job from its backlog of work and invokes it (or “gives it control”), similar to calling a function, and then that job runs. Once it pauses or completes, it returns control to the event loop. The event loop will then select another job from its pool and invoke it. You can _roughly_ think of the collection of jobs as a queue: jobs are added and then processed one at a time, generally (but not always) in order. This process repeats indefinitely, with the event loop cycling endlessly onwards. If there are no more jobs pending execution, the event loop is smart enough to rest and avoid needlessly wasting CPU cycles, and will come back when there’s more work to be done.
Effective execution relies on jobs sharing well and cooperating; a greedy job could hog control and leave the other jobs to starve, rendering the overall event loop approach rather useless.
Copy```
import asyncio

# This creates an event loop and indefinitely cycles through
# its collection of jobs.
event_loop = asyncio.new_event_loop()
event_loop.run_forever()

```

### Asynchronous functions and coroutines[¶](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#asynchronous-functions-and-coroutines "Link to this heading")
This is a basic, boring Python function:
Copy```
def hello_printer():
    print(
        "Hi, I am a lowly, simple printer, though I have all I "
        "need in life -- \nfresh paper and my dearly beloved octopus "
        "partner in crime."
    )

```

Calling a regular function invokes its logic or body:
Copy```
>>> hello_printer()
Hi, I am a lowly, simple printer, though I have all I need in life --
fresh paper and my dearly beloved octopus partner in crime.

```

The [async def](https://docs.python.org/3/reference/compound_stmts.html#async-def), as opposed to just a plain `def`, makes this an asynchronous function (or “coroutine function”). Calling it creates and returns a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine) object.
Copy```
async def loudmouth_penguin(magic_number: int):
    print(
     "I am a super special talking penguin. Far cooler than that printer. "
     f"By the way, my lucky number is: {magic_number}."
    )

```

Calling the async function, `loudmouth_penguin`, does not execute the print statement; instead, it creates a coroutine object:
Copy```
>>> loudmouth_penguin(magic_number=3)
<coroutine object loudmouth_penguin at 0x104ed2740>

```

The terms “coroutine function” and “coroutine object” are often conflated as coroutine. That can be confusing! In this article, coroutine specifically refers to a coroutine object, or more precisely, an instance of [`types.CoroutineType`](https://docs.python.org/3/library/types.html#types.CoroutineType "types.CoroutineType") (native coroutine). Note that coroutines can also exist as instances of [`collections.abc.Coroutine`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Coroutine "collections.abc.Coroutine") – a distinction that matters for type checking.
A coroutine represents the function’s body or logic. A coroutine has to be explicitly started; again, merely creating the coroutine does not start it. Notably, the coroutine can be paused and resumed at various points within the function’s body. That pausing and resuming ability is what allows for asynchronous behavior!
Coroutines and coroutine functions were built by leveraging the functionality of [generators](https://docs.python.org/3/glossary.html#term-generator-iterator) and [generator functions](https://docs.python.org/3/glossary.html#term-generator). Recall, a generator function is a function that [`yield`](https://docs.python.org/3/reference/simple_stmts.html#yield)s, like this one:
Copy```
def get_random_number():
    # This would be a bad random number generator!
    print("Hi")
    yield 1
    print("Hello")
    yield 7
    print("Howdy")
    yield 4
    ...

```

Similar to a coroutine function, calling a generator function does not run it. Instead, it creates a generator object:
Copy```
>>> get_random_number()
<generator object get_random_number at 0x1048671c0>

```

You can proceed to the next `yield` of a generator by using the built-in function [`next()`](https://docs.python.org/3/library/functions.html#next "next"). In other words, the generator runs, then pauses. For example:
Copy```
>>> generator = get_random_number()
>>> next(generator)
Hi
1
>>> next(generator)
Hello
7

```

### Tasks[¶](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#tasks "Link to this heading")
Roughly speaking, [tasks](https://docs.python.org/3/library/asyncio-task.html#asyncio-task-obj) are coroutines (not coroutine functions) tied to an event loop. A task also maintains a list of callback functions whose importance will become clear in a moment when we discuss [`await`](https://docs.python.org/3/reference/expressions.html#await). The recommended way to create tasks is via [`asyncio.create_task()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task "asyncio.create_task").
Creating a task automatically schedules it for execution (by adding a callback to run it in the event loop’s to-do list, that is, collection of jobs).
`asyncio` automatically associates tasks with the event loop for you. This automatic association was purposely designed into `asyncio` for the sake of simplicity. Without it, you’d have to keep track of the event loop object and pass it to any coroutine function that wants to create tasks, adding redundant clutter to your code.
Copy```
coroutine = loudmouth_penguin(magic_number=5)
# This creates a Task object and schedules its execution via the event loop.
task = asyncio.create_task(coroutine)

```

Earlier, we manually created the event loop and set it to run forever. In practice, it’s recommended to use (and common to see) [`asyncio.run()`](https://docs.python.org/3/library/asyncio-runner.html#asyncio.run "asyncio.run"), which takes care of managing the event loop and ensuring the provided coroutine finishes before advancing. For example, many async programs follow this setup:
Copy```
import asyncio

async def main():
    # Perform all sorts of wacky, wild asynchronous things...
    ...

if __name__ == "__main__":
    asyncio.run(main())
    # The program will not reach the following print statement until the
    # coroutine main() finishes.
    print("coroutine main() is done!")

```

It’s important to be aware that the task itself is not added to the event loop, only a callback to the task is. This matters if the task object you created is garbage collected before it’s called by the event loop. For example, consider this program:
Copy```
 1async def hello():
 2    print("hello!")
 3
 4async def main():
 5    asyncio.create_task(hello())
 6    # Other asynchronous instructions which run for a while
 7    # and cede control to the event loop...
 8    ...
 9
10asyncio.run(main())

```

Because there’s no reference to the task object created on line 5, it _might_ be garbage collected before the event loop invokes it. Later instructions in the coroutine `main()` hand control back to the event loop so it can invoke other jobs. When the event loop eventually tries to run the task, it might fail and discover the task object does not exist! This can also happen even if a coroutine keeps a reference to a task but completes before that task finishes. When the coroutine exits, local variables go out of scope and may be subject to garbage collection. In practice, `asyncio` and Python’s garbage collector work pretty hard to ensure this sort of thing doesn’t happen. But that’s no reason to be reckless!
### await[¶](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#await "Link to this heading")
[`await`](https://docs.python.org/3/reference/expressions.html#await) is a Python keyword that’s commonly used in one of two different ways:
Copy```
await task
await coroutine

```

In a crucial way, the behavior of `await` depends on the type of object being awaited.
Awaiting a task will cede control from the current task or coroutine to the event loop. In the process of relinquishing control, a few important things happen. We’ll use the following code example to illustrate:
Copy```
async def plant_a_tree():
    dig_the_hole_task = asyncio.create_task(dig_the_hole())
    await dig_the_hole_task

    # Other instructions associated with planting a tree.
    ...

```

In this example, imagine the event loop has passed control to the start of the coroutine `plant_a_tree()`. As seen above, the coroutine creates a task and then awaits it. The `await dig_the_hole_task` instruction adds a callback (which will resume `plant_a_tree()`) to the `dig_the_hole_task` object’s list of callbacks. And then, the instruction cedes control to the event loop. Some time later, the event loop will pass control to `dig_the_hole_task` and the task will finish whatever it needs to do. Once the task finishes, it will add its various callbacks to the event loop, in this case, a call to resume `plant_a_tree()`.
Generally speaking, when the awaited task finishes (`dig_the_hole_task`), the original task or coroutine (`plant_a_tree()`) is added back to the event loop’s to-do list to be resumed.
This is a basic, yet reliable mental model. In practice, the control handoffs are slightly more complex, but not by much. In part 2, we’ll walk through the details that make this possible.
**Unlike tasks, awaiting a coroutine does not hand control back to the event loop!** Wrapping a coroutine in a task first, then awaiting that would cede control. The behavior of `await coroutine` is effectively the same as invoking a regular, synchronous Python function. Consider this program:
Copy```
import asyncio

async def coro_a():
   print("I am coro_a(). Hi!")

async def coro_b():
   print("I am coro_b(). I sure hope no one hogs the event loop...")

async def main():
   task_b = asyncio.create_task(coro_b())
   num_repeats = 3
   for _ in range(num_repeats):
      await coro_a()
   await task_b

asyncio.run(main())

```

The first statement in the coroutine `main()` creates `task_b` and schedules it for execution via the event loop. Then, `coro_a()` is repeatedly awaited. Control never cedes to the event loop, which is why we see the output of all three `coro_a()` invocations before `coro_b()`’s output:
```
I am coro_a(). Hi!
I am coro_a(). Hi!
I am coro_a(). Hi!
I am coro_b(). I sure hope no one hogs the event loop...

```

If we change `await coro_a()` to `await asyncio.create_task(coro_a())`, the behavior changes. The coroutine `main()` cedes control to the event loop with that statement. The event loop then proceeds through its backlog of work, calling `task_b` and then the task which wraps `coro_a()` before resuming the coroutine `main()`.
```
I am coro_b(). I sure hope no one hogs the event loop...
I am coro_a(). Hi!
I am coro_a(). Hi!
I am coro_a(). Hi!

```

This behavior of `await coroutine` can trip a lot of people up! That example highlights how using only `await coroutine` could unintentionally hog control from other tasks and effectively stall the event loop. [`asyncio.run()`](https://docs.python.org/3/library/asyncio-runner.html#asyncio.run "asyncio.run") can help you detect such occurrences via the `debug=True` flag, which enables [debug mode](https://docs.python.org/3/library/asyncio-dev.html#asyncio-debug-mode). Among other things, it will log any coroutines that monopolize execution for 100ms or longer.
The design intentionally trades off some conceptual clarity around usage of `await` for improved performance. Each time a task is awaited, control needs to be passed all the way up the call stack to the event loop. That might sound minor, but in a large program with many `await` statements and a deep call stack, that overhead can add up to a meaningful performance drag.
## A conceptual overview part 2: the nuts and bolts[¶](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#a-conceptual-overview-part-2-the-nuts-and-bolts "Link to this heading")
Part 2 goes into detail on the mechanisms `asyncio` uses to manage control flow. This is where the magic happens. You’ll come away from this section knowing what `await` does behind the scenes and how to make your own asynchronous operators.
### The inner workings of coroutines[¶](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#the-inner-workings-of-coroutines "Link to this heading")
`asyncio` leverages four components to pass around control.
[`coroutine.send(arg)`](https://docs.python.org/3/reference/expressions.html#generator.send "generator.send") is the method used to start or resume a coroutine. If the coroutine was paused and is now being resumed, the argument `arg` will be sent in as the return value of the `yield` statement which originally paused it. If the coroutine is being used for the first time (as opposed to being resumed), `arg` must be `None`.
Copy```
 1class Rock:
 2    def __await__(self):
 3        value_sent_in = yield 7
 4        print(f"Rock.__await__ resuming with value: {value_sent_in}.")
 5        return value_sent_in
 6
 7async def main():
 8    print("Beginning coroutine main().")
 9    rock = Rock()
10    print("Awaiting rock...")
11    value_from_rock = await rock
12    print(f"Coroutine received value: {value_from_rock} from rock.")
13    return 23
14
15coroutine = main()
16intermediate_result = coroutine.send(None)
17print(f"Coroutine paused and returned intermediate value: {intermediate_result}.")
18
19print(f"Resuming coroutine and sending in value: 42.")
20try:
21    coroutine.send(42)
22except StopIteration as e:
23    returned_value = e.value
24print(f"Coroutine main() finished and provided value: {returned_value}.")

```

[yield](https://docs.python.org/3/reference/expressions.html#yieldexpr), as usual, pauses execution and returns control to the caller. In the example above, the `yield`, on line 3, is called by `... = await rock` on line 11. More broadly speaking, `await` calls the [`__await__()`](https://docs.python.org/3/reference/datamodel.html#object.__await__ "object.__await__") method of the given object. `await` also does one more very special thing: it propagates (or “passes along”) any `yield`s it receives up the call chain. In this case, that’s back to `... = coroutine.send(None)` on line 16.
The coroutine is resumed via the `coroutine.send(42)` call on line 21. The coroutine picks back up from where it `yield`ed (or paused) on line 3 and executes the remaining statements in its body. When a coroutine finishes, it raises a [`StopIteration`](https://docs.python.org/3/library/exceptions.html#StopIteration "StopIteration") exception with the return value attached in the [`value`](https://docs.python.org/3/library/exceptions.html#StopIteration.value "StopIteration.value") attribute.
That snippet produces this output:
```
Beginning coroutine main().
Awaiting rock...
Coroutine paused and returned intermediate value: 7.
Resuming coroutine and sending in value: 42.
Rock.__await__ resuming with value: 42.
Coroutine received value: 42 from rock.
Coroutine main() finished and provided value: 23.

```

It’s worth pausing for a moment here and making sure you followed the various ways that control flow and values were passed. A lot of important ideas were covered and it’s worth ensuring your understanding is firm.
The only way to yield (or effectively cede control) from a coroutine is to `await` an object that `yield`s in its `__await__` method. That might sound odd to you. You might be thinking:
> 1. What about a `yield` directly within the coroutine function? The coroutine function becomes an [async generator function](https://docs.python.org/3/reference/expressions.html#asynchronous-generator-functions), a different beast entirely.
> 2. What about a [yield from](https://docs.python.org/3/reference/expressions.html#yieldexpr) within the coroutine function to a (plain) generator? That causes the error: `SyntaxError: yield from not allowed in a coroutine.` This was intentionally designed for the sake of simplicity – mandating only one way of using coroutines. Initially `yield` was barred as well, but was re-accepted to allow for async generators. Despite that, `yield from` and `await` effectively do the same thing.
### Futures[¶](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#futures "Link to this heading")
A [future](https://docs.python.org/3/library/asyncio-future.html#asyncio-future-obj) is an object meant to represent a computation’s status and result. The term is a nod to the idea of something still to come or not yet happened, and the object is a way to keep an eye on that something.
A future has a few important attributes. One is its state, which can be either “pending”, “cancelled”, or “done”. Another is its result, which is set when the state transitions to done. Unlike a coroutine, a future does not represent the actual computation to be done; instead, it represents the status and result of that computation, kind of like a status light (red, yellow, or green) or indicator.
[`asyncio.Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task") subclasses [`asyncio.Future`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future "asyncio.Future") in order to gain these various capabilities. The prior section said tasks store a list of callbacks, which wasn’t entirely accurate. It’s actually the `Future` class that implements this logic, which `Task` inherits.
Futures may also be used directly (not via tasks). Tasks mark themselves as done when their coroutine is complete. Futures are much more versatile and will be marked as done when you say so. In this way, they’re the flexible interface for you to make your own conditions for waiting and resuming.
### A homemade asyncio.sleep[¶](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#a-homemade-asyncio-sleep "Link to this heading")
We’ll go through an example of how you could leverage a future to create your own variant of asynchronous sleep (`async_sleep`) which mimics [`asyncio.sleep()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.sleep "asyncio.sleep").
This snippet registers a few tasks with the event loop and then awaits the task created by `asyncio.create_task`, which wraps the `async_sleep(3)` coroutine. We want that task to finish only after three seconds have elapsed, but without preventing other tasks from running.
Copy```
async def other_work():
    print("I like work. Work work.")

async def main():
    # Add a few other tasks to the event loop, so there's something
    # to do while asynchronously sleeping.
    work_tasks = [
        asyncio.create_task(other_work()),
        asyncio.create_task(other_work()),
        asyncio.create_task(other_work())
    ]
    print(
        "Beginning asynchronous sleep at time: "
        f"{datetime.datetime.now().strftime("%H:%M:%S")}."
    )
    await asyncio.create_task(async_sleep(3))
    print(
        "Done asynchronous sleep at time: "
        f"{datetime.datetime.now().strftime("%H:%M:%S")}."
    )
    # asyncio.gather effectively awaits each task in the collection.
    await asyncio.gather(*work_tasks)

```

Below, we use a future to enable custom control over when that task will be marked as done. If [`future.set_result()`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.set_result "asyncio.Future.set_result") (the method responsible for marking that future as done) is never called, then this task will never finish. We’ve also enlisted the help of another task, which we’ll see in a moment, that will monitor how much time has elapsed and, accordingly, call `future.set_result()`.
Copy```
async def async_sleep(seconds: float):
    future = asyncio.Future()
    time_to_wake = time.time() + seconds
    # Add the watcher-task to the event loop.
    watcher_task = asyncio.create_task(_sleep_watcher(future, time_to_wake))
    # Block until the future is marked as done.
    await future

```

Below, we use a rather bare `YieldToEventLoop()` object to `yield` from its `__await__` method, ceding control to the event loop. This is effectively the same as calling `asyncio.sleep(0)`, but this approach offers more clarity, not to mention it’s somewhat cheating to use `asyncio.sleep` when showcasing how to implement it!
As usual, the event loop cycles through its tasks, giving them control and receiving control back when they pause or finish. The `watcher_task`, which runs the coroutine `_sleep_watcher(...)`, will be invoked once per full cycle of the event loop. On each resumption, it’ll check the time and if not enough has elapsed, then it’ll pause once again and hand control back to the event loop. Once enough time has elapsed, `_sleep_watcher(...)` marks the future as done and completes by exiting its infinite `while` loop. Given this helper task is only invoked once per cycle of the event loop, you’d be correct to note that this asynchronous sleep will sleep _at least_ three seconds, rather than exactly three seconds. Note this is also true of `asyncio.sleep`.
Copy```
class YieldToEventLoop:
    def __await__(self):
        yield

async def _sleep_watcher(future, time_to_wake):
    while True:
        if time.time() >= time_to_wake:
            # This marks the future as done.
            future.set_result(None)
            break
        else:
            await YieldToEventLoop()

```

Here is the full program’s output:
```
$ python custom-async-sleep.py
Beginning asynchronous sleep at time: 14:52:22.
I like work. Work work.
I like work. Work work.
I like work. Work work.
Done asynchronous sleep at time: 14:52:25.

```

You might feel this implementation of asynchronous sleep was unnecessarily convoluted. And, well, it was. The example was meant to showcase the versatility of futures with a simple example that could be mimicked for more complex needs. For reference, you could implement it without futures, like so:
Copy```
async def simpler_async_sleep(seconds):
    time_to_wake = time.time() + seconds
    while True:
        if time.time() >= time_to_wake:
            return
        else:
            await YieldToEventLoop()

```

But that’s all for now. Hopefully you’re ready to more confidently dive into some async programming or check out advanced topics in the [`rest of the documentation`](https://docs.python.org/3/library/asyncio.html#module-asyncio "asyncio: Asynchronous I/O.").
### [Table of Contents](https://docs.python.org/3/contents.html)
  * [A Conceptual Overview of `asyncio`](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html)
    * [A conceptual overview part 1: the high-level](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#a-conceptual-overview-part-1-the-high-level)
      * [Event Loop](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#event-loop)
      * [Asynchronous functions and coroutines](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#asynchronous-functions-and-coroutines)
      * [Tasks](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#tasks)
      * [await](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#await)
    * [A conceptual overview part 2: the nuts and bolts](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#a-conceptual-overview-part-2-the-nuts-and-bolts)
      * [The inner workings of coroutines](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#the-inner-workings-of-coroutines)
      * [Futures](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#futures)
      * [A homemade asyncio.sleep](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html#a-homemade-asyncio-sleep)


#### Previous topic
[Python HOWTOs](https://docs.python.org/3/howto/index.html "previous chapter")
#### Next topic
[Porting Extension Modules to Python 3](https://docs.python.org/3/howto/cporting.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/howto/a-conceptual-overview-of-asyncio.rst?plain=1)


«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/howto/cporting.html "Porting Extension Modules to Python 3") |
  * [previous](https://docs.python.org/3/howto/index.html "Python HOWTOs") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [Python HOWTOs](https://docs.python.org/3/howto/index.html) »
  * [A Conceptual Overview of `asyncio`](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 


---

<!-- SOURCE: https://docs.python.org/3/library/index.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
#### Previous topic
[10. Full Grammar specification](https://docs.python.org/3/reference/grammar.html "previous chapter")
#### Next topic
[Introduction](https://docs.python.org/3/library/intro.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/index.rst?plain=1)


### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/intro.html "Introduction") |
  * [previous](https://docs.python.org/3/reference/grammar.html "10. Full Grammar specification") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html)
  * | 
  * Theme  Auto Light Dark |


# The Python Standard Library[¶](https://docs.python.org/3/library/index.html#the-python-standard-library "Link to this heading")
While [The Python Language Reference](https://docs.python.org/3/reference/index.html#reference-index) describes the exact syntax and semantics of the Python language, this library reference manual describes the standard library that is distributed with Python. It also describes some of the optional components that are commonly included in Python distributions.
Python’s standard library is very extensive, offering a wide range of facilities as indicated by the long table of contents listed below. The library contains built-in modules (written in C) that provide access to system functionality such as file I/O that would otherwise be inaccessible to Python programmers, as well as modules written in Python that provide standardized solutions for many problems that occur in everyday programming. Some of these modules are explicitly designed to encourage and enhance the portability of Python programs by abstracting away platform-specifics into platform-neutral APIs.
The Python installers for the Windows platform usually include the entire standard library and often also include many additional components. For Unix-like operating systems Python is normally provided as a collection of packages, so it may be necessary to use the packaging tools provided with the operating system to obtain some or all of the optional components.
In addition to the standard library, there is an active collection of hundreds of thousands of components (from individual programs and modules to packages and entire application development frameworks), available from the [Python Package Index](https://pypi.org).
  * [Introduction](https://docs.python.org/3/library/intro.html)
    * [Notes on availability](https://docs.python.org/3/library/intro.html#notes-on-availability)
  * [Built-in Functions](https://docs.python.org/3/library/functions.html)
  * [Built-in Constants](https://docs.python.org/3/library/constants.html)
    * [Constants added by the `site` module](https://docs.python.org/3/library/constants.html#constants-added-by-the-site-module)
  * [Built-in Types](https://docs.python.org/3/library/stdtypes.html)
    * [Truth Value Testing](https://docs.python.org/3/library/stdtypes.html#truth-value-testing)
    * [Boolean Operations — `and`, `or`, `not`](https://docs.python.org/3/library/stdtypes.html#boolean-operations-and-or-not)
    * [Comparisons](https://docs.python.org/3/library/stdtypes.html#comparisons)
    * [Numeric Types — `int`, `float`, `complex`](https://docs.python.org/3/library/stdtypes.html#numeric-types-int-float-complex)
    * [Boolean Type - `bool`](https://docs.python.org/3/library/stdtypes.html#boolean-type-bool)
    * [Iterator Types](https://docs.python.org/3/library/stdtypes.html#iterator-types)
    * [Sequence Types — `list`, `tuple`, `range`](https://docs.python.org/3/library/stdtypes.html#sequence-types-list-tuple-range)
    * [Text and Binary Sequence Type Methods Summary](https://docs.python.org/3/library/stdtypes.html#text-and-binary-sequence-type-methods-summary)
    * [Text Sequence Type — `str`](https://docs.python.org/3/library/stdtypes.html#text-sequence-type-str)
    * [Binary Sequence Types — `bytes`, `bytearray`, `memoryview`](https://docs.python.org/3/library/stdtypes.html#binary-sequence-types-bytes-bytearray-memoryview)
    * [Set Types — `set`, `frozenset`](https://docs.python.org/3/library/stdtypes.html#set-types-set-frozenset)
    * [Mapping Types — `dict`](https://docs.python.org/3/library/stdtypes.html#mapping-types-dict)
    * [Context Manager Types](https://docs.python.org/3/library/stdtypes.html#context-manager-types)
    * [Type Annotation Types — Generic Alias, Union](https://docs.python.org/3/library/stdtypes.html#type-annotation-types-generic-alias-union)
    * [Other Built-in Types](https://docs.python.org/3/library/stdtypes.html#other-built-in-types)
    * [Special Attributes](https://docs.python.org/3/library/stdtypes.html#special-attributes)
    * [Integer string conversion length limitation](https://docs.python.org/3/library/stdtypes.html#integer-string-conversion-length-limitation)
  * [Built-in Exceptions](https://docs.python.org/3/library/exceptions.html)
    * [Exception context](https://docs.python.org/3/library/exceptions.html#exception-context)
    * [Inheriting from built-in exceptions](https://docs.python.org/3/library/exceptions.html#inheriting-from-built-in-exceptions)
    * [Base classes](https://docs.python.org/3/library/exceptions.html#base-classes)
    * [Concrete exceptions](https://docs.python.org/3/library/exceptions.html#concrete-exceptions)
    * [Warnings](https://docs.python.org/3/library/exceptions.html#warnings)
    * [Exception groups](https://docs.python.org/3/library/exceptions.html#exception-groups)
    * [Exception hierarchy](https://docs.python.org/3/library/exceptions.html#exception-hierarchy)
  * [Text Processing Services](https://docs.python.org/3/library/text.html)
    * [`string` — Common string operations](https://docs.python.org/3/library/string.html)
    * [`string.templatelib` — Support for template string literals](https://docs.python.org/3/library/string.templatelib.html)
    * [`re` — Regular expression operations](https://docs.python.org/3/library/re.html)
    * [`difflib` — Helpers for computing deltas](https://docs.python.org/3/library/difflib.html)
    * [`textwrap` — Text wrapping and filling](https://docs.python.org/3/library/textwrap.html)
    * [`unicodedata` — Unicode Database](https://docs.python.org/3/library/unicodedata.html)
    * [`stringprep` — Internet String Preparation](https://docs.python.org/3/library/stringprep.html)
    * [`readline` — GNU readline interface](https://docs.python.org/3/library/readline.html)
    * [`rlcompleter` — Completion function for GNU readline](https://docs.python.org/3/library/rlcompleter.html)
  * [Binary Data Services](https://docs.python.org/3/library/binary.html)
    * [`struct` — Interpret bytes as packed binary data](https://docs.python.org/3/library/struct.html)
    * [`codecs` — Codec registry and base classes](https://docs.python.org/3/library/codecs.html)
  * [Data Types](https://docs.python.org/3/library/datatypes.html)
    * [`datetime` — Basic date and time types](https://docs.python.org/3/library/datetime.html)
    * [`zoneinfo` — IANA time zone support](https://docs.python.org/3/library/zoneinfo.html)
    * [`calendar` — General calendar-related functions](https://docs.python.org/3/library/calendar.html)
    * [`collections` — Container datatypes](https://docs.python.org/3/library/collections.html)
    * [`collections.abc` — Abstract Base Classes for Containers](https://docs.python.org/3/library/collections.abc.html)
    * [`heapq` — Heap queue algorithm](https://docs.python.org/3/library/heapq.html)
    * [`bisect` — Array bisection algorithm](https://docs.python.org/3/library/bisect.html)
    * [`array` — Efficient arrays of numeric values](https://docs.python.org/3/library/array.html)
    * [`weakref` — Weak references](https://docs.python.org/3/library/weakref.html)
    * [`types` — Dynamic type creation and names for built-in types](https://docs.python.org/3/library/types.html)
    * [`copy` — Shallow and deep copy operations](https://docs.python.org/3/library/copy.html)
    * [`pprint` — Data pretty printer](https://docs.python.org/3/library/pprint.html)
    * [`reprlib` — Alternate `repr()` implementation](https://docs.python.org/3/library/reprlib.html)
    * [`enum` — Support for enumerations](https://docs.python.org/3/library/enum.html)
    * [`graphlib` — Functionality to operate with graph-like structures](https://docs.python.org/3/library/graphlib.html)
  * [Numeric and Mathematical Modules](https://docs.python.org/3/library/numeric.html)
    * [`numbers` — Numeric abstract base classes](https://docs.python.org/3/library/numbers.html)
    * [`math` — Mathematical functions](https://docs.python.org/3/library/math.html)
    * [`cmath` — Mathematical functions for complex numbers](https://docs.python.org/3/library/cmath.html)
    * [`decimal` — Decimal fixed-point and floating-point arithmetic](https://docs.python.org/3/library/decimal.html)
    * [`fractions` — Rational numbers](https://docs.python.org/3/library/fractions.html)
    * [`random` — Generate pseudo-random numbers](https://docs.python.org/3/library/random.html)
    * [`statistics` — Mathematical statistics functions](https://docs.python.org/3/library/statistics.html)
  * [Functional Programming Modules](https://docs.python.org/3/library/functional.html)
    * [`itertools` — Functions creating iterators for efficient looping](https://docs.python.org/3/library/itertools.html)
    * [`functools` — Higher-order functions and operations on callable objects](https://docs.python.org/3/library/functools.html)
    * [`operator` — Standard operators as functions](https://docs.python.org/3/library/operator.html)
  * [File and Directory Access](https://docs.python.org/3/library/filesys.html)
    * [`pathlib` — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html)
    * [`os.path` — Common pathname manipulations](https://docs.python.org/3/library/os.path.html)
    * [`stat` — Interpreting `stat()` results](https://docs.python.org/3/library/stat.html)
    * [`filecmp` — File and Directory Comparisons](https://docs.python.org/3/library/filecmp.html)
    * [`tempfile` — Generate temporary files and directories](https://docs.python.org/3/library/tempfile.html)
    * [`glob` — Unix style pathname pattern expansion](https://docs.python.org/3/library/glob.html)
    * [`fnmatch` — Unix filename pattern matching](https://docs.python.org/3/library/fnmatch.html)
    * [`linecache` — Random access to text lines](https://docs.python.org/3/library/linecache.html)
    * [`shutil` — High-level file operations](https://docs.python.org/3/library/shutil.html)
  * [Data Persistence](https://docs.python.org/3/library/persistence.html)
    * [`pickle` — Python object serialization](https://docs.python.org/3/library/pickle.html)
    * [`copyreg` — Register `pickle` support functions](https://docs.python.org/3/library/copyreg.html)
    * [`shelve` — Python object persistence](https://docs.python.org/3/library/shelve.html)
    * [`marshal` — Internal Python object serialization](https://docs.python.org/3/library/marshal.html)
    * [`dbm` — Interfaces to Unix “databases”](https://docs.python.org/3/library/dbm.html)
    * [`sqlite3` — DB-API 2.0 interface for SQLite databases](https://docs.python.org/3/library/sqlite3.html)
  * [Data Compression and Archiving](https://docs.python.org/3/library/archiving.html)
    * [The `compression` package](https://docs.python.org/3/library/compression.html)
    * [`compression.zstd` — Compression compatible with the Zstandard format](https://docs.python.org/3/library/compression.zstd.html)
    * [`zlib` — Compression compatible with **gzip**](https://docs.python.org/3/library/zlib.html)
    * [`gzip` — Support for **gzip** files](https://docs.python.org/3/library/gzip.html)
    * [`bz2` — Support for **bzip2** compression](https://docs.python.org/3/library/bz2.html)
    * [`lzma` — Compression using the LZMA algorithm](https://docs.python.org/3/library/lzma.html)
    * [`zipfile` — Work with ZIP archives](https://docs.python.org/3/library/zipfile.html)
    * [`tarfile` — Read and write tar archive files](https://docs.python.org/3/library/tarfile.html)
  * [File Formats](https://docs.python.org/3/library/fileformats.html)
    * [`csv` — CSV File Reading and Writing](https://docs.python.org/3/library/csv.html)
    * [`configparser` — Configuration file parser](https://docs.python.org/3/library/configparser.html)
    * [`tomllib` — Parse TOML files](https://docs.python.org/3/library/tomllib.html)
    * [`netrc` — netrc file processing](https://docs.python.org/3/library/netrc.html)
    * [`plistlib` — Generate and parse Apple `.plist` files](https://docs.python.org/3/library/plistlib.html)
  * [Cryptographic Services](https://docs.python.org/3/library/crypto.html)
    * [`hashlib` — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html)
    * [`hmac` — Keyed-Hashing for Message Authentication](https://docs.python.org/3/library/hmac.html)
    * [`secrets` — Generate secure random numbers for managing secrets](https://docs.python.org/3/library/secrets.html)
  * [Generic Operating System Services](https://docs.python.org/3/library/allos.html)
    * [`os` — Miscellaneous operating system interfaces](https://docs.python.org/3/library/os.html)
    * [`io` — Core tools for working with streams](https://docs.python.org/3/library/io.html)
    * [`time` — Time access and conversions](https://docs.python.org/3/library/time.html)
    * [`logging` — Logging facility for Python](https://docs.python.org/3/library/logging.html)
    * [`logging.config` — Logging configuration](https://docs.python.org/3/library/logging.config.html)
    * [`logging.handlers` — Logging handlers](https://docs.python.org/3/library/logging.handlers.html)
    * [`platform` — Access to underlying platform’s identifying data](https://docs.python.org/3/library/platform.html)
    * [`errno` — Standard errno system symbols](https://docs.python.org/3/library/errno.html)
    * [`ctypes` — A foreign function library for Python](https://docs.python.org/3/library/ctypes.html)
  * [Command-line interface libraries](https://docs.python.org/3/library/cmdlinelibs.html)
    * [`argparse` — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html)
    * [`optparse` — Parser for command line options](https://docs.python.org/3/library/optparse.html)
    * [`getpass` — Portable password input](https://docs.python.org/3/library/getpass.html)
    * [`fileinput` — Iterate over lines from multiple input streams](https://docs.python.org/3/library/fileinput.html)
    * [`curses` — Terminal handling for character-cell displays](https://docs.python.org/3/library/curses.html)
    * [`curses.textpad` — Text input widget for curses programs](https://docs.python.org/3/library/curses.html#module-curses.textpad)
    * [`curses.ascii` — Utilities for ASCII characters](https://docs.python.org/3/library/curses.ascii.html)
    * [`curses.panel` — A panel stack extension for curses](https://docs.python.org/3/library/curses.panel.html)
    * [`cmd` — Support for line-oriented command interpreters](https://docs.python.org/3/library/cmd.html)
  * [Concurrent Execution](https://docs.python.org/3/library/concurrency.html)
    * [`threading` — Thread-based parallelism](https://docs.python.org/3/library/threading.html)
    * [`multiprocessing` — Process-based parallelism](https://docs.python.org/3/library/multiprocessing.html)
    * [`multiprocessing.shared_memory` — Shared memory for direct access across processes](https://docs.python.org/3/library/multiprocessing.shared_memory.html)
    * [The `concurrent` package](https://docs.python.org/3/library/concurrent.html)
    * [`concurrent.futures` — Launching parallel tasks](https://docs.python.org/3/library/concurrent.futures.html)
    * [`concurrent.interpreters` — Multiple interpreters in the same process](https://docs.python.org/3/library/concurrent.interpreters.html)
    * [`subprocess` — Subprocess management](https://docs.python.org/3/library/subprocess.html)
    * [`sched` — Event scheduler](https://docs.python.org/3/library/sched.html)
    * [`queue` — A synchronized queue class](https://docs.python.org/3/library/queue.html)
    * [`contextvars` — Context Variables](https://docs.python.org/3/library/contextvars.html)
    * [`_thread` — Low-level threading API](https://docs.python.org/3/library/_thread.html)
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html)
    * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html)
    * [`socket` — Low-level networking interface](https://docs.python.org/3/library/socket.html)
    * [`ssl` — TLS/SSL wrapper for socket objects](https://docs.python.org/3/library/ssl.html)
    * [`select` — Waiting for I/O completion](https://docs.python.org/3/library/select.html)
    * [`selectors` — High-level I/O multiplexing](https://docs.python.org/3/library/selectors.html)
    * [`signal` — Set handlers for asynchronous events](https://docs.python.org/3/library/signal.html)
    * [`mmap` — Memory-mapped file support](https://docs.python.org/3/library/mmap.html)
  * [Internet Data Handling](https://docs.python.org/3/library/netdata.html)
    * [`email` — An email and MIME handling package](https://docs.python.org/3/library/email.html)
    * [`json` — JSON encoder and decoder](https://docs.python.org/3/library/json.html)
    * [`mailbox` — Manipulate mailboxes in various formats](https://docs.python.org/3/library/mailbox.html)
    * [`mimetypes` — Map filenames to MIME types](https://docs.python.org/3/library/mimetypes.html)
    * [`base64` — Base16, Base32, Base64, Base85 Data Encodings](https://docs.python.org/3/library/base64.html)
    * [`binascii` — Convert between binary and ASCII](https://docs.python.org/3/library/binascii.html)
    * [`quopri` — Encode and decode MIME quoted-printable data](https://docs.python.org/3/library/quopri.html)
  * [Structured Markup Processing Tools](https://docs.python.org/3/library/markup.html)
    * [`html` — HyperText Markup Language support](https://docs.python.org/3/library/html.html)
    * [`html.parser` — Simple HTML and XHTML parser](https://docs.python.org/3/library/html.parser.html)
    * [`html.entities` — Definitions of HTML general entities](https://docs.python.org/3/library/html.entities.html)
    * [XML Processing Modules](https://docs.python.org/3/library/xml.html)
    * [`xml.etree.ElementTree` — The ElementTree XML API](https://docs.python.org/3/library/xml.etree.elementtree.html)
    * [`xml.dom` — The Document Object Model API](https://docs.python.org/3/library/xml.dom.html)
    * [`xml.dom.minidom` — Minimal DOM implementation](https://docs.python.org/3/library/xml.dom.minidom.html)
    * [`xml.dom.pulldom` — Support for building partial DOM trees](https://docs.python.org/3/library/xml.dom.pulldom.html)
    * [`xml.sax` — Support for SAX2 parsers](https://docs.python.org/3/library/xml.sax.html)
    * [`xml.sax.handler` — Base classes for SAX handlers](https://docs.python.org/3/library/xml.sax.handler.html)
    * [`xml.sax.saxutils` — SAX Utilities](https://docs.python.org/3/library/xml.sax.utils.html)
    * [`xml.sax.xmlreader` — Interface for XML parsers](https://docs.python.org/3/library/xml.sax.reader.html)
    * [`xml.parsers.expat` — Fast XML parsing using Expat](https://docs.python.org/3/library/pyexpat.html)
  * [Internet Protocols and Support](https://docs.python.org/3/library/internet.html)
    * [`webbrowser` — Convenient web-browser controller](https://docs.python.org/3/library/webbrowser.html)
    * [`wsgiref` — WSGI Utilities and Reference Implementation](https://docs.python.org/3/library/wsgiref.html)
    * [`urllib` — URL handling modules](https://docs.python.org/3/library/urllib.html)
    * [`urllib.request` — Extensible library for opening URLs](https://docs.python.org/3/library/urllib.request.html)
    * [`urllib.response` — Response classes used by urllib](https://docs.python.org/3/library/urllib.request.html#module-urllib.response)
    * [`urllib.parse` — Parse URLs into components](https://docs.python.org/3/library/urllib.parse.html)
    * [`urllib.error` — Exception classes raised by urllib.request](https://docs.python.org/3/library/urllib.error.html)
    * [`urllib.robotparser` — Parser for robots.txt](https://docs.python.org/3/library/urllib.robotparser.html)
    * [`http` — HTTP modules](https://docs.python.org/3/library/http.html)
    * [`http.client` — HTTP protocol client](https://docs.python.org/3/library/http.client.html)
    * [`ftplib` — FTP protocol client](https://docs.python.org/3/library/ftplib.html)
    * [`poplib` — POP3 protocol client](https://docs.python.org/3/library/poplib.html)
    * [`imaplib` — IMAP4 protocol client](https://docs.python.org/3/library/imaplib.html)
    * [`smtplib` — SMTP protocol client](https://docs.python.org/3/library/smtplib.html)
    * [`uuid` — UUID objects according to **RFC 9562**](https://docs.python.org/3/library/uuid.html)
    * [`socketserver` — A framework for network servers](https://docs.python.org/3/library/socketserver.html)
    * [`http.server` — HTTP servers](https://docs.python.org/3/library/http.server.html)
    * [`http.cookies` — HTTP state management](https://docs.python.org/3/library/http.cookies.html)
    * [`http.cookiejar` — Cookie handling for HTTP clients](https://docs.python.org/3/library/http.cookiejar.html)
    * [`xmlrpc` — XMLRPC server and client modules](https://docs.python.org/3/library/xmlrpc.html)
    * [`xmlrpc.client` — XML-RPC client access](https://docs.python.org/3/library/xmlrpc.client.html)
    * [`xmlrpc.server` — Basic XML-RPC servers](https://docs.python.org/3/library/xmlrpc.server.html)
    * [`ipaddress` — IPv4/IPv6 manipulation library](https://docs.python.org/3/library/ipaddress.html)
  * [Multimedia Services](https://docs.python.org/3/library/mm.html)
    * [`wave` — Read and write WAV files](https://docs.python.org/3/library/wave.html)
    * [`colorsys` — Conversions between color systems](https://docs.python.org/3/library/colorsys.html)
  * [Internationalization](https://docs.python.org/3/library/i18n.html)
    * [`gettext` — Multilingual internationalization services](https://docs.python.org/3/library/gettext.html)
    * [`locale` — Internationalization services](https://docs.python.org/3/library/locale.html)
  * [Graphical user interfaces with Tk](https://docs.python.org/3/library/tk.html)
    * [`tkinter` — Python interface to Tcl/Tk](https://docs.python.org/3/library/tkinter.html)
    * [`tkinter.colorchooser` — Color choosing dialog](https://docs.python.org/3/library/tkinter.colorchooser.html)
    * [`tkinter.font` — Tkinter font wrapper](https://docs.python.org/3/library/tkinter.font.html)
    * [Tkinter Dialogs](https://docs.python.org/3/library/dialog.html)
    * [`tkinter.messagebox` — Tkinter message prompts](https://docs.python.org/3/library/tkinter.messagebox.html)
    * [`tkinter.scrolledtext` — Scrolled Text Widget](https://docs.python.org/3/library/tkinter.scrolledtext.html)
    * [`tkinter.dnd` — Drag and drop support](https://docs.python.org/3/library/tkinter.dnd.html)
    * [`tkinter.ttk` — Tk themed widgets](https://docs.python.org/3/library/tkinter.ttk.html)
    * [IDLE — Python editor and shell](https://docs.python.org/3/library/idle.html)
    * [`turtle` — Turtle graphics](https://docs.python.org/3/library/turtle.html)
  * [Development Tools](https://docs.python.org/3/library/development.html)
    * [`typing` — Support for type hints](https://docs.python.org/3/library/typing.html)
    * [`pydoc` — Documentation generator and online help system](https://docs.python.org/3/library/pydoc.html)
    * [Python Development Mode](https://docs.python.org/3/library/devmode.html)
    * [`doctest` — Test interactive Python examples](https://docs.python.org/3/library/doctest.html)
    * [`unittest` — Unit testing framework](https://docs.python.org/3/library/unittest.html)
    * [`unittest.mock` — mock object library](https://docs.python.org/3/library/unittest.mock.html)
    * [`unittest.mock` — getting started](https://docs.python.org/3/library/unittest.mock-examples.html)
    * [`test` — Regression tests package for Python](https://docs.python.org/3/library/test.html)
    * [`test.support` — Utilities for the Python test suite](https://docs.python.org/3/library/test.html#module-test.support)
    * [`test.support.socket_helper` — Utilities for socket tests](https://docs.python.org/3/library/test.html#module-test.support.socket_helper)
    * [`test.support.script_helper` — Utilities for the Python execution tests](https://docs.python.org/3/library/test.html#module-test.support.script_helper)
    * [`test.support.bytecode_helper` — Support tools for testing correct bytecode generation](https://docs.python.org/3/library/test.html#module-test.support.bytecode_helper)
    * [`test.support.threading_helper` — Utilities for threading tests](https://docs.python.org/3/library/test.html#module-test.support.threading_helper)
    * [`test.support.os_helper` — Utilities for os tests](https://docs.python.org/3/library/test.html#module-test.support.os_helper)
    * [`test.support.import_helper` — Utilities for import tests](https://docs.python.org/3/library/test.html#module-test.support.import_helper)
    * [`test.support.warnings_helper` — Utilities for warnings tests](https://docs.python.org/3/library/test.html#module-test.support.warnings_helper)
  * [Debugging and Profiling](https://docs.python.org/3/library/debug.html)
    * [Audit events table](https://docs.python.org/3/library/audit_events.html)
    * [`bdb` — Debugger framework](https://docs.python.org/3/library/bdb.html)
    * [`faulthandler` — Dump the Python traceback](https://docs.python.org/3/library/faulthandler.html)
    * [`pdb` — The Python Debugger](https://docs.python.org/3/library/pdb.html)
    * [The Python Profilers](https://docs.python.org/3/library/profile.html)
    * [`timeit` — Measure execution time of small code snippets](https://docs.python.org/3/library/timeit.html)
    * [`trace` — Trace or track Python statement execution](https://docs.python.org/3/library/trace.html)
    * [`tracemalloc` — Trace memory allocations](https://docs.python.org/3/library/tracemalloc.html)
  * [Software Packaging and Distribution](https://docs.python.org/3/library/distribution.html)
    * [`ensurepip` — Bootstrapping the `pip` installer](https://docs.python.org/3/library/ensurepip.html)
    * [`venv` — Creation of virtual environments](https://docs.python.org/3/library/venv.html)
    * [`zipapp` — Manage executable Python zip archives](https://docs.python.org/3/library/zipapp.html)
  * [Python Runtime Services](https://docs.python.org/3/library/python.html)
    * [`sys` — System-specific parameters and functions](https://docs.python.org/3/library/sys.html)
    * [`sys.monitoring` — Execution event monitoring](https://docs.python.org/3/library/sys.monitoring.html)
    * [`sysconfig` — Provide access to Python’s configuration information](https://docs.python.org/3/library/sysconfig.html)
    * [`builtins` — Built-in objects](https://docs.python.org/3/library/builtins.html)
    * [`__main__` — Top-level code environment](https://docs.python.org/3/library/__main__.html)
    * [`warnings` — Warning control](https://docs.python.org/3/library/warnings.html)
    * [`dataclasses` — Data Classes](https://docs.python.org/3/library/dataclasses.html)
    * [`contextlib` — Utilities for `with`-statement contexts](https://docs.python.org/3/library/contextlib.html)
    * [`abc` — Abstract Base Classes](https://docs.python.org/3/library/abc.html)
    * [`atexit` — Exit handlers](https://docs.python.org/3/library/atexit.html)
    * [`traceback` — Print or retrieve a stack traceback](https://docs.python.org/3/library/traceback.html)
    * [`__future__` — Future statement definitions](https://docs.python.org/3/library/__future__.html)
    * [`gc` — Garbage Collector interface](https://docs.python.org/3/library/gc.html)
    * [`inspect` — Inspect live objects](https://docs.python.org/3/library/inspect.html)
    * [`annotationlib` — Functionality for introspecting annotations](https://docs.python.org/3/library/annotationlib.html)
    * [`site` — Site-specific configuration hook](https://docs.python.org/3/library/site.html)
  * [Custom Python Interpreters](https://docs.python.org/3/library/custominterp.html)
    * [`code` — Interpreter base classes](https://docs.python.org/3/library/code.html)
    * [`codeop` — Compile Python code](https://docs.python.org/3/library/codeop.html)
  * [Importing Modules](https://docs.python.org/3/library/modules.html)
    * [`zipimport` — Import modules from Zip archives](https://docs.python.org/3/library/zipimport.html)
    * [`pkgutil` — Package extension utility](https://docs.python.org/3/library/pkgutil.html)
    * [`modulefinder` — Find modules used by a script](https://docs.python.org/3/library/modulefinder.html)
    * [`runpy` — Locating and executing Python modules](https://docs.python.org/3/library/runpy.html)
    * [`importlib` — The implementation of `import`](https://docs.python.org/3/library/importlib.html)
    * [`importlib.resources` – Package resource reading, opening and access](https://docs.python.org/3/library/importlib.resources.html)
    * [`importlib.resources.abc` – Abstract base classes for resources](https://docs.python.org/3/library/importlib.resources.abc.html)
    * [`importlib.metadata` – Accessing package metadata](https://docs.python.org/3/library/importlib.metadata.html)
    * [The initialization of the `sys.path` module search path](https://docs.python.org/3/library/sys_path_init.html)
  * [Python Language Services](https://docs.python.org/3/library/language.html)
    * [`ast` — Abstract syntax trees](https://docs.python.org/3/library/ast.html)
    * [`symtable` — Access to the compiler’s symbol tables](https://docs.python.org/3/library/symtable.html)
    * [`token` — Constants used with Python parse trees](https://docs.python.org/3/library/token.html)
    * [`keyword` — Testing for Python keywords](https://docs.python.org/3/library/keyword.html)
    * [`tokenize` — Tokenizer for Python source](https://docs.python.org/3/library/tokenize.html)
    * [`tabnanny` — Detection of ambiguous indentation](https://docs.python.org/3/library/tabnanny.html)
    * [`pyclbr` — Python module browser support](https://docs.python.org/3/library/pyclbr.html)
    * [`py_compile` — Compile Python source files](https://docs.python.org/3/library/py_compile.html)
    * [`compileall` — Byte-compile Python libraries](https://docs.python.org/3/library/compileall.html)
    * [`dis` — Disassembler for Python bytecode](https://docs.python.org/3/library/dis.html)
    * [`pickletools` — Tools for pickle developers](https://docs.python.org/3/library/pickletools.html)
  * [MS Windows Specific Services](https://docs.python.org/3/library/windows.html)
    * [`msvcrt` — Useful routines from the MS VC++ runtime](https://docs.python.org/3/library/msvcrt.html)
    * [`winreg` — Windows registry access](https://docs.python.org/3/library/winreg.html)
    * [`winsound` — Sound-playing interface for Windows](https://docs.python.org/3/library/winsound.html)
  * [Unix-specific services](https://docs.python.org/3/library/unix.html)
    * [`shlex` — Simple lexical analysis](https://docs.python.org/3/library/shlex.html)
    * [`posix` — The most common POSIX system calls](https://docs.python.org/3/library/posix.html)
    * [`pwd` — The password database](https://docs.python.org/3/library/pwd.html)
    * [`grp` — The group database](https://docs.python.org/3/library/grp.html)
    * [`termios` — POSIX style tty control](https://docs.python.org/3/library/termios.html)
    * [`tty` — Terminal control functions](https://docs.python.org/3/library/tty.html)
    * [`pty` — Pseudo-terminal utilities](https://docs.python.org/3/library/pty.html)
    * [`fcntl` — The `fcntl` and `ioctl` system calls](https://docs.python.org/3/library/fcntl.html)
    * [`resource` — Resource usage information](https://docs.python.org/3/library/resource.html)
    * [`syslog` — Unix syslog library routines](https://docs.python.org/3/library/syslog.html)
  * [Modules command-line interface (CLI)](https://docs.python.org/3/library/cmdline.html)
  * [Superseded Modules](https://docs.python.org/3/library/superseded.html)
    * [`getopt` — C-style parser for command line options](https://docs.python.org/3/library/getopt.html)
  * [Removed Modules](https://docs.python.org/3/library/removed.html)
  * [Security Considerations](https://docs.python.org/3/library/security_warnings.html)


#### Previous topic
[10. Full Grammar specification](https://docs.python.org/3/reference/grammar.html "previous chapter")
#### Next topic
[Introduction](https://docs.python.org/3/library/intro.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/index.rst?plain=1)


«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/intro.html "Introduction") |
  * [previous](https://docs.python.org/3/reference/grammar.html "10. Full Grammar specification") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 


---

<!-- SOURCE: https://docs.python.org/3/library/asyncio-runner.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
### [Table of Contents](https://docs.python.org/3/contents.html)
  * [Runners](https://docs.python.org/3/library/asyncio-runner.html)
    * [Running an asyncio Program](https://docs.python.org/3/library/asyncio-runner.html#running-an-asyncio-program)
    * [Runner context manager](https://docs.python.org/3/library/asyncio-runner.html#runner-context-manager)
    * [Handling Keyboard Interruption](https://docs.python.org/3/library/asyncio-runner.html#handling-keyboard-interruption)


#### Previous topic
[`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html "previous chapter")
#### Next topic
[Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio-runner.rst?plain=1)


### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-task.html "Coroutines and Tasks") |
  * [previous](https://docs.python.org/3/library/asyncio.html "asyncio — Asynchronous I/O") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html) »
  * [Runners](https://docs.python.org/3/library/asyncio-runner.html)
  * | 
  * Theme  Auto Light Dark |


# Runners[¶](https://docs.python.org/3/library/asyncio-runner.html#runners "Link to this heading")
**Source code:** [Lib/asyncio/runners.py](https://github.com/python/cpython/tree/3.14/Lib/asyncio/runners.py)
This section outlines high-level asyncio primitives to run asyncio code.
They are built on top of an [event loop](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio-event-loop) with the aim to simplify async code usage for common wide-spread scenarios.
  * [Running an asyncio Program](https://docs.python.org/3/library/asyncio-runner.html#running-an-asyncio-program)
  * [Runner context manager](https://docs.python.org/3/library/asyncio-runner.html#runner-context-manager)
  * [Handling Keyboard Interruption](https://docs.python.org/3/library/asyncio-runner.html#handling-keyboard-interruption)


##  [Running an asyncio Program](https://docs.python.org/3/library/asyncio-runner.html#id1)[¶](https://docs.python.org/3/library/asyncio-runner.html#running-an-asyncio-program "Link to this heading") 

asyncio.run(_coro_ , _*_ , _debug =None_, _loop_factory =None_)[¶](https://docs.python.org/3/library/asyncio-runner.html#asyncio.run "Link to this definition") 
    
Execute _coro_ in an asyncio event loop and return the result.
The argument can be any awaitable object.
This function runs the awaitable, taking care of managing the asyncio event loop, _finalizing asynchronous generators_ , and closing the executor.
This function cannot be called when another asyncio event loop is running in the same thread.
If _debug_ is `True`, the event loop will be run in debug mode. `False` disables debug mode explicitly. `None` is used to respect the global [Debug Mode](https://docs.python.org/3/library/asyncio-dev.html#asyncio-debug-mode) settings.
If _loop_factory_ is not `None`, it is used to create a new event loop; otherwise [`asyncio.new_event_loop()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.new_event_loop "asyncio.new_event_loop") is used. The loop is closed at the end. This function should be used as a main entry point for asyncio programs, and should ideally only be called once. It is recommended to use _loop_factory_ to configure the event loop instead of policies. Passing [`asyncio.EventLoop`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.EventLoop "asyncio.EventLoop") allows running asyncio without the policy system.
The executor is given a timeout duration of 5 minutes to shutdown. If the executor hasn’t finished within that duration, a warning is emitted and the executor is closed.
Example:
Copy```
async def main():
    await asyncio.sleep(1)
    print('hello')

asyncio.run(main())

```

Added in version 3.7.
Changed in version 3.9: Updated to use [`loop.shutdown_default_executor()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.shutdown_default_executor "asyncio.loop.shutdown_default_executor").
Changed in version 3.10: _debug_ is `None` by default to respect the global debug mode settings.
Changed in version 3.12: Added _loop_factory_ parameter.
Changed in version 3.14: _coro_ can be any awaitable object.
Note
The `asyncio` policy system is deprecated and will be removed in Python 3.16; from there on, an explicit _loop_factory_ is needed to configure the event loop.
##  [Runner context manager](https://docs.python.org/3/library/asyncio-runner.html#id2)[¶](https://docs.python.org/3/library/asyncio-runner.html#runner-context-manager "Link to this heading") 

_class_ asyncio.Runner(_*_ , _debug =None_, _loop_factory =None_)[¶](https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner "Link to this definition") 
    
A context manager that simplifies _multiple_ async function calls in the same context.
Sometimes several top-level async functions should be called in the same [event loop](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio-event-loop) and [`contextvars.Context`](https://docs.python.org/3/library/contextvars.html#contextvars.Context "contextvars.Context").
If _debug_ is `True`, the event loop will be run in debug mode. `False` disables debug mode explicitly. `None` is used to respect the global [Debug Mode](https://docs.python.org/3/library/asyncio-dev.html#asyncio-debug-mode) settings.
_loop_factory_ could be used for overriding the loop creation. It is the responsibility of the _loop_factory_ to set the created loop as the current one. By default [`asyncio.new_event_loop()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.new_event_loop "asyncio.new_event_loop") is used and set as current event loop with [`asyncio.set_event_loop()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.set_event_loop "asyncio.set_event_loop") if _loop_factory_ is `None`.
Basically, [`asyncio.run()`](https://docs.python.org/3/library/asyncio-runner.html#asyncio.run "asyncio.run") example can be rewritten with the runner usage:
Copy```
async def main():
    await asyncio.sleep(1)
    print('hello')

with asyncio.Runner() as runner:
    runner.run(main())

```

Added in version 3.11. 

run(_coro_ , _*_ , _context =None_)[¶](https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner.run "Link to this definition") 
    
Execute _coro_ in the embedded event loop.
The argument can be any awaitable object.
If the argument is a coroutine, it is wrapped in a Task.
An optional keyword-only _context_ argument allows specifying a custom [`contextvars.Context`](https://docs.python.org/3/library/contextvars.html#contextvars.Context "contextvars.Context") for the code to run in. The runner’s default context is used if context is `None`.
Returns the awaitable’s result or raises an exception.
This function cannot be called when another asyncio event loop is running in the same thread.
Changed in version 3.14: _coro_ can be any awaitable object. 

close()[¶](https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner.close "Link to this definition") 
    
Close the runner.
Finalize asynchronous generators, shutdown default executor, close the event loop and release embedded [`contextvars.Context`](https://docs.python.org/3/library/contextvars.html#contextvars.Context "contextvars.Context"). 

get_loop()[¶](https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner.get_loop "Link to this definition") 
    
Return the event loop associated with the runner instance.
Note
[`Runner`](https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner "asyncio.Runner") uses the lazy initialization strategy, its constructor doesn’t initialize underlying low-level structures.
Embedded _loop_ and _context_ are created at the [`with`](https://docs.python.org/3/reference/compound_stmts.html#with) body entering or the first call of [`run()`](https://docs.python.org/3/library/asyncio-runner.html#asyncio.run "asyncio.run") or [`get_loop()`](https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner.get_loop "asyncio.Runner.get_loop").
##  [Handling Keyboard Interruption](https://docs.python.org/3/library/asyncio-runner.html#id3)[¶](https://docs.python.org/3/library/asyncio-runner.html#handling-keyboard-interruption "Link to this heading")
Added in version 3.11.
When [`signal.SIGINT`](https://docs.python.org/3/library/signal.html#signal.SIGINT "signal.SIGINT") is raised by `Ctrl`-`C`, [`KeyboardInterrupt`](https://docs.python.org/3/library/exceptions.html#KeyboardInterrupt "KeyboardInterrupt") exception is raised in the main thread by default. However this doesn’t work with [`asyncio`](https://docs.python.org/3/library/asyncio.html#module-asyncio "asyncio: Asynchronous I/O.") because it can interrupt asyncio internals and can hang the program from exiting.
To mitigate this issue, [`asyncio`](https://docs.python.org/3/library/asyncio.html#module-asyncio "asyncio: Asynchronous I/O.") handles [`signal.SIGINT`](https://docs.python.org/3/library/signal.html#signal.SIGINT "signal.SIGINT") as follows:
  1. [`asyncio.Runner.run()`](https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner.run "asyncio.Runner.run") installs a custom [`signal.SIGINT`](https://docs.python.org/3/library/signal.html#signal.SIGINT "signal.SIGINT") handler before any user code is executed and removes it when exiting from the function.
  2. The [`Runner`](https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner "asyncio.Runner") creates the main task for the passed coroutine for its execution.
  3. When [`signal.SIGINT`](https://docs.python.org/3/library/signal.html#signal.SIGINT "signal.SIGINT") is raised by `Ctrl`-`C`, the custom signal handler cancels the main task by calling [`asyncio.Task.cancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel "asyncio.Task.cancel") which raises [`asyncio.CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") inside the main task. This causes the Python stack to unwind, `try/except` and `try/finally` blocks can be used for resource cleanup. After the main task is cancelled, [`asyncio.Runner.run()`](https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner.run "asyncio.Runner.run") raises [`KeyboardInterrupt`](https://docs.python.org/3/library/exceptions.html#KeyboardInterrupt "KeyboardInterrupt").
  4. A user could write a tight loop which cannot be interrupted by [`asyncio.Task.cancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel "asyncio.Task.cancel"), in which case the second following `Ctrl`-`C` immediately raises the [`KeyboardInterrupt`](https://docs.python.org/3/library/exceptions.html#KeyboardInterrupt "KeyboardInterrupt") without cancelling the main task.


### [Table of Contents](https://docs.python.org/3/contents.html)
  * [Runners](https://docs.python.org/3/library/asyncio-runner.html)
    * [Running an asyncio Program](https://docs.python.org/3/library/asyncio-runner.html#running-an-asyncio-program)
    * [Runner context manager](https://docs.python.org/3/library/asyncio-runner.html#runner-context-manager)
    * [Handling Keyboard Interruption](https://docs.python.org/3/library/asyncio-runner.html#handling-keyboard-interruption)


#### Previous topic
[`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html "previous chapter")
#### Next topic
[Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio-runner.rst?plain=1)


«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-task.html "Coroutines and Tasks") |
  * [previous](https://docs.python.org/3/library/asyncio.html "asyncio — Asynchronous I/O") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html) »
  * [Runners](https://docs.python.org/3/library/asyncio-runner.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 
  *[*]: Keyword-only parameters separator (PEP 3102)


---

<!-- SOURCE: https://docs.python.org/3/py-modindex.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [Python Module Index](https://docs.python.org/3/py-modindex.html)
  * | 
  * Theme  Auto Light Dark |


# Python Module Index
[**_**](https://docs.python.org/3/py-modindex.html#cap-_) | [**a**](https://docs.python.org/3/py-modindex.html#cap-a) | [**b**](https://docs.python.org/3/py-modindex.html#cap-b) | [**c**](https://docs.python.org/3/py-modindex.html#cap-c) | [**d**](https://docs.python.org/3/py-modindex.html#cap-d) | [**e**](https://docs.python.org/3/py-modindex.html#cap-e) | [**f**](https://docs.python.org/3/py-modindex.html#cap-f) | [**g**](https://docs.python.org/3/py-modindex.html#cap-g) | [**h**](https://docs.python.org/3/py-modindex.html#cap-h) | [**i**](https://docs.python.org/3/py-modindex.html#cap-i) | [**j**](https://docs.python.org/3/py-modindex.html#cap-j) | [**k**](https://docs.python.org/3/py-modindex.html#cap-k) | [**l**](https://docs.python.org/3/py-modindex.html#cap-l) | [**m**](https://docs.python.org/3/py-modindex.html#cap-m) | [**n**](https://docs.python.org/3/py-modindex.html#cap-n) | [**o**](https://docs.python.org/3/py-modindex.html#cap-o) | [**p**](https://docs.python.org/3/py-modindex.html#cap-p) | [**q**](https://docs.python.org/3/py-modindex.html#cap-q) | [**r**](https://docs.python.org/3/py-modindex.html#cap-r) | [**s**](https://docs.python.org/3/py-modindex.html#cap-s) | [**t**](https://docs.python.org/3/py-modindex.html#cap-t) | [**u**](https://docs.python.org/3/py-modindex.html#cap-u) | [**v**](https://docs.python.org/3/py-modindex.html#cap-v) | [**w**](https://docs.python.org/3/py-modindex.html#cap-w) | [**x**](https://docs.python.org/3/py-modindex.html#cap-x) | [**z**](https://docs.python.org/3/py-modindex.html#cap-z)
|  |   
---|---|---  
|  **_** |   
|  [`__future__`](https://docs.python.org/3/library/__future__.html#module-__future__) |  _Future statement definitions_  
|  [`__main__`](https://docs.python.org/3/library/__main__.html#module-__main__) |  _The environment where top-level code is run. Covers command-line interfaces, import-time behavior, and ``__name__ == '__main__'``._  
|  [`_thread`](https://docs.python.org/3/library/_thread.html#module-_thread) |  _Low-level threading API._  
|  [`_tkinter`](https://docs.python.org/3/library/tkinter.html#module-_tkinter) |  _A binary module that contains the low-level interface to Tcl/Tk._  
|  |   
|  **a** |   
|  [`abc`](https://docs.python.org/3/library/abc.html#module-abc) |  _Abstract base classes according to :pep:`3119`._  
|  [`aifc`](https://docs.python.org/3/library/aifc.html#module-aifc) |  **Deprecated:** _Removed in 3.13._  
|  [`annotationlib`](https://docs.python.org/3/library/annotationlib.html#module-annotationlib) |  _Functionality for introspecting annotations_  
|  [`argparse`](https://docs.python.org/3/library/argparse.html#module-argparse) |  _Command-line option and argument parsing library._  
|  [`array`](https://docs.python.org/3/library/array.html#module-array) |  _Space efficient arrays of uniformly typed numeric values._  
|  [`ast`](https://docs.python.org/3/library/ast.html#module-ast) |  _Abstract Syntax Tree classes and manipulation._  
|  [`asynchat`](https://docs.python.org/3/library/asynchat.html#module-asynchat) |  **Deprecated:** _Removed in 3.12._  
|  [`asyncio`](https://docs.python.org/3/library/asyncio.html#module-asyncio) |  _Asynchronous I/O._  
|  [`asyncore`](https://docs.python.org/3/library/asyncore.html#module-asyncore) |  **Deprecated:** _Removed in 3.12._  
|  [`atexit`](https://docs.python.org/3/library/atexit.html#module-atexit) |  _Register and execute cleanup functions._  
|  [`audioop`](https://docs.python.org/3/library/audioop.html#module-audioop) |  **Deprecated:** _Removed in 3.13._  
|  |   
|  **b** |   
|  [`base64`](https://docs.python.org/3/library/base64.html#module-base64) |  _RFC 4648: Base16, Base32, Base64 Data Encodings; Base85 and Ascii85_  
|  [`bdb`](https://docs.python.org/3/library/bdb.html#module-bdb) |  _Debugger framework._  
|  [`binascii`](https://docs.python.org/3/library/binascii.html#module-binascii) |  _Tools for converting between binary and various ASCII-encoded binary representations._  
|  [`bisect`](https://docs.python.org/3/library/bisect.html#module-bisect) |  _Array bisection algorithms for binary searching._  
|  [`builtins`](https://docs.python.org/3/library/builtins.html#module-builtins) |  _The module that provides the built-in namespace._  
|  [`bz2`](https://docs.python.org/3/library/bz2.html#module-bz2) |  _Interfaces for bzip2 compression and decompression._  
|  |   
|  **c** |   
|  [`calendar`](https://docs.python.org/3/library/calendar.html#module-calendar) |  _Functions for working with calendars, including some emulation of the Unix cal program._  
|  [`cgi`](https://docs.python.org/3/library/cgi.html#module-cgi) |  **Deprecated:** _Removed in 3.13._  
|  [`cgitb`](https://docs.python.org/3/library/cgitb.html#module-cgitb) |  **Deprecated:** _Removed in 3.13._  
|  [`chunk`](https://docs.python.org/3/library/chunk.html#module-chunk) |  **Deprecated:** _Removed in 3.13._  
|  [`cmath`](https://docs.python.org/3/library/cmath.html#module-cmath) |  _Mathematical functions for complex numbers._  
|  [`cmd`](https://docs.python.org/3/library/cmd.html#module-cmd) |  _Build line-oriented command interpreters._  
|  [`code`](https://docs.python.org/3/library/code.html#module-code) |  _Facilities to implement read-eval-print loops._  
|  [`codecs`](https://docs.python.org/3/library/codecs.html#module-codecs) |  _Encode and decode data and streams._  
|  [`codeop`](https://docs.python.org/3/library/codeop.html#module-codeop) |  _Compile (possibly incomplete) Python code._  
![-](https://docs.python.org/3/_static/plus.png) |  [`collections`](https://docs.python.org/3/library/collections.html#module-collections) |  _Container datatypes_  
|  [`collections.abc`](https://docs.python.org/3/library/collections.abc.html#module-collections.abc) |  _Abstract base classes for containers_  
|  [`colorsys`](https://docs.python.org/3/library/colorsys.html#module-colorsys) |  _Conversion functions between RGB and other color systems._  
|  [`compileall`](https://docs.python.org/3/library/compileall.html#module-compileall) |  _Tools for byte-compiling all Python source files in a directory tree._  
![-](https://docs.python.org/3/_static/plus.png) |  [`compression`](https://docs.python.org/3/library/compression.html#module-compression) |   
|  [`compression.zstd`](https://docs.python.org/3/library/compression.zstd.html#module-compression.zstd) |  _Low-level interface to compression and decompression routines in the zstd library._  
![-](https://docs.python.org/3/_static/plus.png) |  `concurrent` |   
|  [`concurrent.futures`](https://docs.python.org/3/library/concurrent.futures.html#module-concurrent.futures) |  _Execute computations concurrently using threads or processes._  
|  [`concurrent.interpreters`](https://docs.python.org/3/library/concurrent.interpreters.html#module-concurrent.interpreters) |  _Multiple interpreters in the same process_  
|  [`configparser`](https://docs.python.org/3/library/configparser.html#module-configparser) |  _Configuration file parser._  
|  [`contextlib`](https://docs.python.org/3/library/contextlib.html#module-contextlib) |  _Utilities for with-statement contexts._  
|  [`contextvars`](https://docs.python.org/3/library/contextvars.html#module-contextvars) |  _Context Variables_  
|  [`copy`](https://docs.python.org/3/library/copy.html#module-copy) |  _Shallow and deep copy operations._  
|  [`copyreg`](https://docs.python.org/3/library/copyreg.html#module-copyreg) |  _Register pickle support functions._  
|  [`cProfile`](https://docs.python.org/3/library/profile.html#module-cProfile) |   
|  [`crypt`](https://docs.python.org/3/library/crypt.html#module-crypt) |  **Deprecated:** _Removed in 3.13._  
|  [`csv`](https://docs.python.org/3/library/csv.html#module-csv) |  _Write and read tabular data to and from delimited files._  
|  [`ctypes`](https://docs.python.org/3/library/ctypes.html#module-ctypes) |  _A foreign function library for Python._  
![-](https://docs.python.org/3/_static/plus.png) |  [`curses`](https://docs.python.org/3/library/curses.html#module-curses) _(Unix)_ |  _An interface to the curses library, providing portable terminal handling._  
|  [`curses.ascii`](https://docs.python.org/3/library/curses.ascii.html#module-curses.ascii) |  _Constants and set-membership functions for ASCII characters._  
|  [`curses.panel`](https://docs.python.org/3/library/curses.panel.html#module-curses.panel) |  _A panel stack extension that adds depth to curses windows._  
|  [`curses.textpad`](https://docs.python.org/3/library/curses.html#module-curses.textpad) |  _Emacs-like input editing in a curses window._  
|  |   
|  **d** |   
|  [`dataclasses`](https://docs.python.org/3/library/dataclasses.html#module-dataclasses) |  _Generate special methods on user-defined classes._  
|  [`datetime`](https://docs.python.org/3/library/datetime.html#module-datetime) |  _Basic date and time types._  
![-](https://docs.python.org/3/_static/plus.png) |  [`dbm`](https://docs.python.org/3/library/dbm.html#module-dbm) |  _Interfaces to various Unix "database" formats._  
|  [`dbm.dumb`](https://docs.python.org/3/library/dbm.html#module-dbm.dumb) |  _Portable implementation of the simple DBM interface._  
|  [`dbm.gnu`](https://docs.python.org/3/library/dbm.html#module-dbm.gnu) _(Unix)_ |  _GNU database manager_  
|  [`dbm.ndbm`](https://docs.python.org/3/library/dbm.html#module-dbm.ndbm) _(Unix)_ |  _The New Database Manager_  
|  [`dbm.sqlite3`](https://docs.python.org/3/library/dbm.html#module-dbm.sqlite3) _(All)_ |  _SQLite backend for dbm_  
|  [`decimal`](https://docs.python.org/3/library/decimal.html#module-decimal) |  _Implementation of the General Decimal Arithmetic Specification._  
|  [`difflib`](https://docs.python.org/3/library/difflib.html#module-difflib) |  _Helpers for computing differences between objects._  
|  [`dis`](https://docs.python.org/3/library/dis.html#module-dis) |  _Disassembler for Python bytecode._  
|  [`distutils`](https://docs.python.org/3/library/distutils.html#module-distutils) |  **Deprecated:** _Removed in 3.12._  
|  [`doctest`](https://docs.python.org/3/library/doctest.html#module-doctest) |  _Test pieces of code within docstrings._  
|  |   
|  **e** |   
![-](https://docs.python.org/3/_static/plus.png) |  [`email`](https://docs.python.org/3/library/email.html#module-email) |  _Package supporting the parsing, manipulating, and generating email messages._  
|  [`email.charset`](https://docs.python.org/3/library/email.charset.html#module-email.charset) |  _Character Sets_  
|  [`email.contentmanager`](https://docs.python.org/3/library/email.contentmanager.html#module-email.contentmanager) |  _Storing and Retrieving Content from MIME Parts_  
|  [`email.encoders`](https://docs.python.org/3/library/email.encoders.html#module-email.encoders) |  _Encoders for email message payloads._  
|  [`email.errors`](https://docs.python.org/3/library/email.errors.html#module-email.errors) |  _The exception classes used by the email package._  
|  [`email.generator`](https://docs.python.org/3/library/email.generator.html#module-email.generator) |  _Generate flat text email messages from a message structure._  
|  [`email.header`](https://docs.python.org/3/library/email.header.html#module-email.header) |  _Representing non-ASCII headers_  
|  [`email.headerregistry`](https://docs.python.org/3/library/email.headerregistry.html#module-email.headerregistry) |  _Automatic Parsing of headers based on the field name_  
|  [`email.iterators`](https://docs.python.org/3/library/email.iterators.html#module-email.iterators) |  _Iterate over a message object tree._  
|  [`email.message`](https://docs.python.org/3/library/email.message.html#module-email.message) |  _The base class representing email messages._  
|  [`email.mime`](https://docs.python.org/3/library/email.mime.html#module-email.mime) |  _Build MIME messages._  
|  [`email.mime.application`](https://docs.python.org/3/library/email.mime.html#module-email.mime.application) |   
|  [`email.mime.audio`](https://docs.python.org/3/library/email.mime.html#module-email.mime.audio) |   
|  [`email.mime.base`](https://docs.python.org/3/library/email.mime.html#module-email.mime.base) |   
|  [`email.mime.image`](https://docs.python.org/3/library/email.mime.html#module-email.mime.image) |   
|  [`email.mime.message`](https://docs.python.org/3/library/email.mime.html#module-email.mime.message) |   
|  [`email.mime.multipart`](https://docs.python.org/3/library/email.mime.html#module-email.mime.multipart) |   
|  [`email.mime.nonmultipart`](https://docs.python.org/3/library/email.mime.html#module-email.mime.nonmultipart) |   
|  [`email.mime.text`](https://docs.python.org/3/library/email.mime.html#module-email.mime.text) |   
|  [`email.parser`](https://docs.python.org/3/library/email.parser.html#module-email.parser) |  _Parse flat text email messages to produce a message object structure._  
|  [`email.policy`](https://docs.python.org/3/library/email.policy.html#module-email.policy) |  _Controlling the parsing and generating of messages_  
|  [`email.utils`](https://docs.python.org/3/library/email.utils.html#module-email.utils) |  _Miscellaneous email package utilities._  
![-](https://docs.python.org/3/_static/plus.png) |  [`encodings`](https://docs.python.org/3/library/codecs.html#module-encodings) |  _Encodings package_  
|  [`encodings.idna`](https://docs.python.org/3/library/codecs.html#module-encodings.idna) |  _Internationalized Domain Names implementation_  
|  [`encodings.mbcs`](https://docs.python.org/3/library/codecs.html#module-encodings.mbcs) |  _Windows ANSI codepage_  
|  [`encodings.utf_8_sig`](https://docs.python.org/3/library/codecs.html#module-encodings.utf_8_sig) |  _UTF-8 codec with BOM signature_  
|  [`ensurepip`](https://docs.python.org/3/library/ensurepip.html#module-ensurepip) |  _Bootstrapping the "pip" installer into an existing Python installation or virtual environment._  
|  [`enum`](https://docs.python.org/3/library/enum.html#module-enum) |  _Implementation of an enumeration class._  
|  [`errno`](https://docs.python.org/3/library/errno.html#module-errno) |  _Standard errno system symbols._  
|  |   
|  **f** |   
|  [`faulthandler`](https://docs.python.org/3/library/faulthandler.html#module-faulthandler) |  _Dump the Python traceback._  
|  [`fcntl`](https://docs.python.org/3/library/fcntl.html#module-fcntl) _(Unix)_ |  _The fcntl() and ioctl() system calls._  
|  [`filecmp`](https://docs.python.org/3/library/filecmp.html#module-filecmp) |  _Compare files efficiently._  
|  [`fileinput`](https://docs.python.org/3/library/fileinput.html#module-fileinput) |  _Loop over standard input or a list of files._  
|  [`fnmatch`](https://docs.python.org/3/library/fnmatch.html#module-fnmatch) |  _Unix shell style filename pattern matching._  
|  [`fractions`](https://docs.python.org/3/library/fractions.html#module-fractions) |  _Rational numbers._  
|  [`ftplib`](https://docs.python.org/3/library/ftplib.html#module-ftplib) |  _FTP protocol client (requires sockets)._  
|  [`functools`](https://docs.python.org/3/library/functools.html#module-functools) |  _Higher-order functions and operations on callable objects._  
|  |   
|  **g** |   
|  [`gc`](https://docs.python.org/3/library/gc.html#module-gc) |  _Interface to the cycle-detecting garbage collector._  
|  [`getopt`](https://docs.python.org/3/library/getopt.html#module-getopt) |  _Portable parser for command line options; support both short and long option names._  
|  [`getpass`](https://docs.python.org/3/library/getpass.html#module-getpass) |  _Portable reading of passwords and retrieval of the userid._  
|  [`gettext`](https://docs.python.org/3/library/gettext.html#module-gettext) |  _Multilingual internationalization services._  
|  [`glob`](https://docs.python.org/3/library/glob.html#module-glob) |  _Unix shell style pathname pattern expansion._  
|  [`graphlib`](https://docs.python.org/3/library/graphlib.html#module-graphlib) |  _Functionality to operate with graph-like structures_  
|  [`grp`](https://docs.python.org/3/library/grp.html#module-grp) _(Unix)_ |  _The group database (getgrnam() and friends)._  
|  [`gzip`](https://docs.python.org/3/library/gzip.html#module-gzip) |  _Interfaces for gzip compression and decompression using file objects._  
|  |   
|  **h** |   
|  [`hashlib`](https://docs.python.org/3/library/hashlib.html#module-hashlib) |  _Secure hash and message digest algorithms._  
|  [`heapq`](https://docs.python.org/3/library/heapq.html#module-heapq) |  _Heap queue algorithm (a.k.a. priority queue)._  
|  [`hmac`](https://docs.python.org/3/library/hmac.html#module-hmac) |  _Keyed-Hashing for Message Authentication (HMAC) implementation_  
![-](https://docs.python.org/3/_static/plus.png) |  [`html`](https://docs.python.org/3/library/html.html#module-html) |  _Helpers for manipulating HTML._  
|  [`html.entities`](https://docs.python.org/3/library/html.entities.html#module-html.entities) |  _Definitions of HTML general entities._  
|  [`html.parser`](https://docs.python.org/3/library/html.parser.html#module-html.parser) |  _A simple parser that can handle HTML and XHTML._  
![-](https://docs.python.org/3/_static/plus.png) |  [`http`](https://docs.python.org/3/library/http.html#module-http) |  _HTTP status codes and messages_  
|  [`http.client`](https://docs.python.org/3/library/http.client.html#module-http.client) |  _HTTP and HTTPS protocol client (requires sockets)._  
|  [`http.cookiejar`](https://docs.python.org/3/library/http.cookiejar.html#module-http.cookiejar) |  _Classes for automatic handling of HTTP cookies._  
|  [`http.cookies`](https://docs.python.org/3/library/http.cookies.html#module-http.cookies) |  _Support for HTTP state management (cookies)._  
|  [`http.server`](https://docs.python.org/3/library/http.server.html#module-http.server) |  _HTTP server and request handlers._  
|  |   
|  **i** |   
|  [`idlelib`](https://docs.python.org/3/library/idle.html#module-idlelib) |  _Implementation package for the IDLE shell/editor._  
|  [`imaplib`](https://docs.python.org/3/library/imaplib.html#module-imaplib) |  _IMAP4 protocol client (requires sockets)._  
|  [`imghdr`](https://docs.python.org/3/library/imghdr.html#module-imghdr) |  **Deprecated:** _Removed in 3.13._  
|  [`imp`](https://docs.python.org/3/library/imp.html#module-imp) |  **Deprecated:** _Removed in 3.12._  
![-](https://docs.python.org/3/_static/plus.png) |  [`importlib`](https://docs.python.org/3/library/importlib.html#module-importlib) |  _The implementation of the import machinery._  
|  [`importlib.abc`](https://docs.python.org/3/library/importlib.html#module-importlib.abc) |  _Abstract base classes related to import_  
|  [`importlib.machinery`](https://docs.python.org/3/library/importlib.html#module-importlib.machinery) |  _Importers and path hooks_  
|  [`importlib.metadata`](https://docs.python.org/3/library/importlib.metadata.html#module-importlib.metadata) |  _Accessing package metadata_  
|  [`importlib.resources`](https://docs.python.org/3/library/importlib.resources.html#module-importlib.resources) |  _Package resource reading, opening, and access_  
|  [`importlib.resources.abc`](https://docs.python.org/3/library/importlib.resources.abc.html#module-importlib.resources.abc) |  _Abstract base classes for resources_  
|  [`importlib.util`](https://docs.python.org/3/library/importlib.html#module-importlib.util) |  _Utility code for importers_  
|  [`inspect`](https://docs.python.org/3/library/inspect.html#module-inspect) |  _Extract information and source code from live objects._  
|  [`io`](https://docs.python.org/3/library/io.html#module-io) |  _Core tools for working with streams._  
|  [`ipaddress`](https://docs.python.org/3/library/ipaddress.html#module-ipaddress) |  _IPv4/IPv6 manipulation library._  
|  [`itertools`](https://docs.python.org/3/library/itertools.html#module-itertools) |  _Functions creating iterators for efficient looping._  
|  |   
|  **j** |   
![-](https://docs.python.org/3/_static/plus.png) |  [`json`](https://docs.python.org/3/library/json.html#module-json) |  _Encode and decode the JSON format._  
|  [`json.tool`](https://docs.python.org/3/library/json.html#module-json.tool) |  _A command-line interface to validate and pretty-print JSON._  
|  |   
|  **k** |   
|  [`keyword`](https://docs.python.org/3/library/keyword.html#module-keyword) |  _Test whether a string is a keyword in Python._  
|  |   
|  **l** |   
|  [`linecache`](https://docs.python.org/3/library/linecache.html#module-linecache) |  _Provides random access to individual lines from text files._  
|  [`locale`](https://docs.python.org/3/library/locale.html#module-locale) |  _Internationalization services._  
![-](https://docs.python.org/3/_static/plus.png) |  [`logging`](https://docs.python.org/3/library/logging.html#module-logging) |  _Flexible event logging system for applications._  
|  [`logging.config`](https://docs.python.org/3/library/logging.config.html#module-logging.config) |  _Configuration of the logging module._  
|  [`logging.handlers`](https://docs.python.org/3/library/logging.handlers.html#module-logging.handlers) |  _Handlers for the logging module._  
|  [`lzma`](https://docs.python.org/3/library/lzma.html#module-lzma) |  _A Python wrapper for the liblzma compression library._  
|  |   
|  **m** |   
|  [`mailbox`](https://docs.python.org/3/library/mailbox.html#module-mailbox) |  _Manipulate mailboxes in various formats_  
|  [`mailcap`](https://docs.python.org/3/library/mailcap.html#module-mailcap) |  **Deprecated:** _Removed in 3.13._  
|  [`marshal`](https://docs.python.org/3/library/marshal.html#module-marshal) |  _Convert Python objects to streams of bytes and back (with different constraints)._  
|  [`math`](https://docs.python.org/3/library/math.html#module-math) |  _Mathematical functions (sin() etc.)._  
|  [`mimetypes`](https://docs.python.org/3/library/mimetypes.html#module-mimetypes) |  _Mapping of filename extensions to MIME types._  
|  [`mmap`](https://docs.python.org/3/library/mmap.html#module-mmap) |  _Interface to memory-mapped files for Unix and Windows._  
|  [`modulefinder`](https://docs.python.org/3/library/modulefinder.html#module-modulefinder) |  _Find modules used by a script._  
|  [`msilib`](https://docs.python.org/3/library/msilib.html#module-msilib) |  **Deprecated:** _Removed in 3.13._  
|  [`msvcrt`](https://docs.python.org/3/library/msvcrt.html#module-msvcrt) _(Windows)_ |  _Miscellaneous useful routines from the MS VC++ runtime._  
![-](https://docs.python.org/3/_static/plus.png) |  [`multiprocessing`](https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing) |  _Process-based parallelism._  
|  [`multiprocessing.connection`](https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing.connection) |  _API for dealing with sockets._  
|  [`multiprocessing.dummy`](https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing.dummy) |  _Dumb wrapper around threading._  
|  [`multiprocessing.managers`](https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing.managers) |  _Share data between process with shared objects._  
|  [`multiprocessing.pool`](https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing.pool) |  _Create pools of processes._  
|  [`multiprocessing.shared_memory`](https://docs.python.org/3/library/multiprocessing.shared_memory.html#module-multiprocessing.shared_memory) |  _Provides shared memory for direct access across processes._  
|  [`multiprocessing.sharedctypes`](https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing.sharedctypes) |  _Allocate ctypes objects from shared memory._  
|  |   
|  **n** |   
|  [`netrc`](https://docs.python.org/3/library/netrc.html#module-netrc) |  _Loading of .netrc files._  
|  [`nis`](https://docs.python.org/3/library/nis.html#module-nis) |  **Deprecated:** _Removed in 3.13._  
|  [`nntplib`](https://docs.python.org/3/library/nntplib.html#module-nntplib) |  **Deprecated:** _Removed in 3.13._  
|  [`numbers`](https://docs.python.org/3/library/numbers.html#module-numbers) |  _Numeric abstract base classes (Complex, Real, Integral, etc.)._  
|  |   
|  **o** |   
|  [`operator`](https://docs.python.org/3/library/operator.html#module-operator) |  _Functions corresponding to the standard operators._  
|  [`optparse`](https://docs.python.org/3/library/optparse.html#module-optparse) |  _Command-line option parsing library._  
![-](https://docs.python.org/3/_static/plus.png) |  [`os`](https://docs.python.org/3/library/os.html#module-os) |  _Miscellaneous operating system interfaces._  
|  [`os.path`](https://docs.python.org/3/library/os.path.html#module-os.path) |  _Operations on pathnames._  
|  [`ossaudiodev`](https://docs.python.org/3/library/ossaudiodev.html#module-ossaudiodev) |  **Deprecated:** _Removed in 3.13._  
|  |   
|  **p** |   
![-](https://docs.python.org/3/_static/plus.png) |  [`pathlib`](https://docs.python.org/3/library/pathlib.html#module-pathlib) |  _Object-oriented filesystem paths_  
|  [`pathlib.types`](https://docs.python.org/3/library/pathlib.html#module-pathlib.types) |  _pathlib types for static type checking_  
|  [`pdb`](https://docs.python.org/3/library/pdb.html#module-pdb) |  _The Python debugger for interactive interpreters._  
|  [`pickle`](https://docs.python.org/3/library/pickle.html#module-pickle) |  _Convert Python objects to streams of bytes and back._  
|  [`pickletools`](https://docs.python.org/3/library/pickletools.html#module-pickletools) |  _Contains extensive comments about the pickle protocols and pickle-machine opcodes, as well as some useful functions._  
|  [`pipes`](https://docs.python.org/3/library/pipes.html#module-pipes) |  **Deprecated:** _Removed in 3.13._  
|  [`pkgutil`](https://docs.python.org/3/library/pkgutil.html#module-pkgutil) |  _Utilities for the import system._  
|  [`platform`](https://docs.python.org/3/library/platform.html#module-platform) |  _Retrieves as much platform identifying data as possible._  
|  [`plistlib`](https://docs.python.org/3/library/plistlib.html#module-plistlib) |  _Generate and parse Apple plist files._  
|  [`poplib`](https://docs.python.org/3/library/poplib.html#module-poplib) |  _POP3 protocol client (requires sockets)._  
|  [`posix`](https://docs.python.org/3/library/posix.html#module-posix) _(Unix)_ |  _The most common POSIX system calls (normally used via module os)._  
|  [`pprint`](https://docs.python.org/3/library/pprint.html#module-pprint) |  _Data pretty printer._  
|  [`profile`](https://docs.python.org/3/library/profile.html#module-profile) |  _Python source profiler._  
|  [`pstats`](https://docs.python.org/3/library/profile.html#module-pstats) |  _Statistics object for use with the profiler._  
|  [`pty`](https://docs.python.org/3/library/pty.html#module-pty) _(Unix)_ |  _Pseudo-Terminal Handling for Unix._  
|  [`pwd`](https://docs.python.org/3/library/pwd.html#module-pwd) _(Unix)_ |  _The password database (getpwnam() and friends)._  
|  [`py_compile`](https://docs.python.org/3/library/py_compile.html#module-py_compile) |  _Generate byte-code files from Python source files._  
|  [`pyclbr`](https://docs.python.org/3/library/pyclbr.html#module-pyclbr) |  _Supports information extraction for a Python module browser._  
|  [`pydoc`](https://docs.python.org/3/library/pydoc.html#module-pydoc) |  _Documentation generator and online help system._  
|  |   
|  **q** |   
|  [`queue`](https://docs.python.org/3/library/queue.html#module-queue) |  _A synchronized queue class._  
|  [`quopri`](https://docs.python.org/3/library/quopri.html#module-quopri) |  _Encode and decode files using the MIME quoted-printable encoding._  
|  |   
|  **r** |   
|  [`random`](https://docs.python.org/3/library/random.html#module-random) |  _Generate pseudo-random numbers with various common distributions._  
|  [`re`](https://docs.python.org/3/library/re.html#module-re) |  _Regular expression operations._  
|  [`readline`](https://docs.python.org/3/library/readline.html#module-readline) _(Unix)_ |  _GNU readline support for Python._  
|  [`reprlib`](https://docs.python.org/3/library/reprlib.html#module-reprlib) |  _Alternate repr() implementation with size limits._  
|  [`resource`](https://docs.python.org/3/library/resource.html#module-resource) _(Unix)_ |  _An interface to provide resource usage information on the current process._  
|  [`rlcompleter`](https://docs.python.org/3/library/rlcompleter.html#module-rlcompleter) |  _Python identifier completion, suitable for the GNU readline library._  
|  [`runpy`](https://docs.python.org/3/library/runpy.html#module-runpy) |  _Locate and run Python modules without importing them first._  
|  |   
|  **s** |   
|  [`sched`](https://docs.python.org/3/library/sched.html#module-sched) |  _General purpose event scheduler._  
|  [`secrets`](https://docs.python.org/3/library/secrets.html#module-secrets) |  _Generate secure random numbers for managing secrets._  
|  [`select`](https://docs.python.org/3/library/select.html#module-select) |  _Wait for I/O completion on multiple streams._  
|  [`selectors`](https://docs.python.org/3/library/selectors.html#module-selectors) |  _High-level I/O multiplexing._  
|  [`shelve`](https://docs.python.org/3/library/shelve.html#module-shelve) |  _Python object persistence._  
|  [`shlex`](https://docs.python.org/3/library/shlex.html#module-shlex) |  _Simple lexical analysis for Unix shell-like languages._  
|  [`shutil`](https://docs.python.org/3/library/shutil.html#module-shutil) |  _High-level file operations, including copying._  
|  [`signal`](https://docs.python.org/3/library/signal.html#module-signal) |  _Set handlers for asynchronous events._  
|  [`site`](https://docs.python.org/3/library/site.html#module-site) |  _Module responsible for site-specific configuration._  
|  [`sitecustomize`](https://docs.python.org/3/library/site.html#module-sitecustomize) |   
|  [`smtpd`](https://docs.python.org/3/library/smtpd.html#module-smtpd) |  **Deprecated:** _Removed in 3.12._  
|  [`smtplib`](https://docs.python.org/3/library/smtplib.html#module-smtplib) |  _SMTP protocol client (requires sockets)._  
|  [`sndhdr`](https://docs.python.org/3/library/sndhdr.html#module-sndhdr) |  **Deprecated:** _Removed in 3.13._  
|  [`socket`](https://docs.python.org/3/library/socket.html#module-socket) |  _Low-level networking interface._  
|  [`socketserver`](https://docs.python.org/3/library/socketserver.html#module-socketserver) |  _A framework for network servers._  
|  [`spwd`](https://docs.python.org/3/library/spwd.html#module-spwd) |  **Deprecated:** _Removed in 3.13._  
|  [`sqlite3`](https://docs.python.org/3/library/sqlite3.html#module-sqlite3) |  _A DB-API 2.0 implementation using SQLite 3.x._  
|  [`ssl`](https://docs.python.org/3/library/ssl.html#module-ssl) |  _TLS/SSL wrapper for socket objects_  
|  [`stat`](https://docs.python.org/3/library/stat.html#module-stat) |  _Utilities for interpreting the results of os.stat(), os.lstat() and os.fstat()._  
|  [`statistics`](https://docs.python.org/3/library/statistics.html#module-statistics) |  _Mathematical statistics functions_  
![-](https://docs.python.org/3/_static/plus.png) |  [`string`](https://docs.python.org/3/library/string.html#module-string) |  _Common string operations._  
|  [`string.templatelib`](https://docs.python.org/3/library/string.templatelib.html#module-string.templatelib) |  _Support for template string literals._  
|  [`stringprep`](https://docs.python.org/3/library/stringprep.html#module-stringprep) |  _String preparation, as per RFC 3453_  
|  [`struct`](https://docs.python.org/3/library/struct.html#module-struct) |  _Interpret bytes as packed binary data._  
|  [`subprocess`](https://docs.python.org/3/library/subprocess.html#module-subprocess) |  _Subprocess management._  
|  [`sunau`](https://docs.python.org/3/library/sunau.html#module-sunau) |  **Deprecated:** _Removed in 3.13._  
|  [`symtable`](https://docs.python.org/3/library/symtable.html#module-symtable) |  _Interface to the compiler's internal symbol tables._  
![-](https://docs.python.org/3/_static/plus.png) |  [`sys`](https://docs.python.org/3/library/sys.html#module-sys) |  _Access system-specific parameters and functions._  
|  [`sys.monitoring`](https://docs.python.org/3/library/sys.monitoring.html#module-sys.monitoring) |  _Access and control event monitoring_  
|  [`sysconfig`](https://docs.python.org/3/library/sysconfig.html#module-sysconfig) |  _Python's configuration information_  
|  [`syslog`](https://docs.python.org/3/library/syslog.html#module-syslog) _(Unix)_ |  _An interface to the Unix syslog library routines._  
|  |   
|  **t** |   
|  [`tabnanny`](https://docs.python.org/3/library/tabnanny.html#module-tabnanny) |  _Tool for detecting white space related problems in Python source files in a directory tree._  
|  [`tarfile`](https://docs.python.org/3/library/tarfile.html#module-tarfile) |  _Read and write tar-format archive files._  
|  [`telnetlib`](https://docs.python.org/3/library/telnetlib.html#module-telnetlib) |  **Deprecated:** _Removed in 3.13._  
|  [`tempfile`](https://docs.python.org/3/library/tempfile.html#module-tempfile) |  _Generate temporary files and directories._  
|  [`termios`](https://docs.python.org/3/library/termios.html#module-termios) _(Unix)_ |  _POSIX style tty control._  
![-](https://docs.python.org/3/_static/plus.png) |  [`test`](https://docs.python.org/3/library/test.html#module-test) |  _Regression tests package containing the testing suite for Python._  
|  [`test.regrtest`](https://docs.python.org/3/library/test.html#module-test.regrtest) |  _Drives the regression test suite._  
|  [`test.support`](https://docs.python.org/3/library/test.html#module-test.support) |  _Support for Python's regression test suite._  
|  [`test.support.bytecode_helper`](https://docs.python.org/3/library/test.html#module-test.support.bytecode_helper) |  _Support tools for testing correct bytecode generation._  
|  [`test.support.import_helper`](https://docs.python.org/3/library/test.html#module-test.support.import_helper) |  _Support for import tests._  
|  [`test.support.os_helper`](https://docs.python.org/3/library/test.html#module-test.support.os_helper) |  _Support for os tests._  
|  [`test.support.script_helper`](https://docs.python.org/3/library/test.html#module-test.support.script_helper) |  _Support for Python's script execution tests._  
|  [`test.support.socket_helper`](https://docs.python.org/3/library/test.html#module-test.support.socket_helper) |  _Support for socket tests._  
|  [`test.support.threading_helper`](https://docs.python.org/3/library/test.html#module-test.support.threading_helper) |  _Support for threading tests._  
|  [`test.support.warnings_helper`](https://docs.python.org/3/library/test.html#module-test.support.warnings_helper) |  _Support for warnings tests._  
|  [`textwrap`](https://docs.python.org/3/library/textwrap.html#module-textwrap) |  _Text wrapping and filling_  
|  [`threading`](https://docs.python.org/3/library/threading.html#module-threading) |  _Thread-based parallelism._  
|  [`time`](https://docs.python.org/3/library/time.html#module-time) |  _Time access and conversions._  
|  [`timeit`](https://docs.python.org/3/library/timeit.html#module-timeit) |  _Measure the execution time of small code snippets._  
![-](https://docs.python.org/3/_static/plus.png) |  [`tkinter`](https://docs.python.org/3/library/tkinter.html#module-tkinter) |  _Interface to Tcl/Tk for graphical user interfaces_  
|  [`tkinter.colorchooser`](https://docs.python.org/3/library/tkinter.colorchooser.html#module-tkinter.colorchooser) _(Tk)_ |  _Color choosing dialog_  
|  [`tkinter.commondialog`](https://docs.python.org/3/library/dialog.html#module-tkinter.commondialog) _(Tk)_ |  _Tkinter base class for dialogs_  
|  [`tkinter.dnd`](https://docs.python.org/3/library/tkinter.dnd.html#module-tkinter.dnd) _(Tk)_ |  _Tkinter drag-and-drop interface_  
|  [`tkinter.filedialog`](https://docs.python.org/3/library/dialog.html#module-tkinter.filedialog) _(Tk)_ |  _Dialog classes for file selection_  
|  [`tkinter.font`](https://docs.python.org/3/library/tkinter.font.html#module-tkinter.font) _(Tk)_ |  _Tkinter font-wrapping class_  
|  [`tkinter.messagebox`](https://docs.python.org/3/library/tkinter.messagebox.html#module-tkinter.messagebox) _(Tk)_ |  _Various types of alert dialogs_  
|  [`tkinter.scrolledtext`](https://docs.python.org/3/library/tkinter.scrolledtext.html#module-tkinter.scrolledtext) _(Tk)_ |  _Text widget with a vertical scroll bar._  
|  [`tkinter.simpledialog`](https://docs.python.org/3/library/dialog.html#module-tkinter.simpledialog) _(Tk)_ |  _Simple dialog windows_  
|  [`tkinter.ttk`](https://docs.python.org/3/library/tkinter.ttk.html#module-tkinter.ttk) |  _Tk themed widget set_  
|  [`token`](https://docs.python.org/3/library/token.html#module-token) |  _Constants representing terminal nodes of the parse tree._  
|  [`tokenize`](https://docs.python.org/3/library/tokenize.html#module-tokenize) |  _Lexical scanner for Python source code._  
|  [`tomllib`](https://docs.python.org/3/library/tomllib.html#module-tomllib) |  _Parse TOML files._  
|  [`trace`](https://docs.python.org/3/library/trace.html#module-trace) |  _Trace or track Python statement execution._  
|  [`traceback`](https://docs.python.org/3/library/traceback.html#module-traceback) |  _Print or retrieve a stack traceback._  
|  [`tracemalloc`](https://docs.python.org/3/library/tracemalloc.html#module-tracemalloc) |  _Trace memory allocations._  
|  [`tty`](https://docs.python.org/3/library/tty.html#module-tty) _(Unix)_ |  _Utility functions that perform common terminal control operations._  
|  [`turtle`](https://docs.python.org/3/library/turtle.html#module-turtle) |  _An educational framework for simple graphics applications_  
|  [`turtledemo`](https://docs.python.org/3/library/turtle.html#module-turtledemo) |  _A viewer for example turtle scripts_  
|  [`types`](https://docs.python.org/3/library/types.html#module-types) |  _Names for built-in types._  
|  [`typing`](https://docs.python.org/3/library/typing.html#module-typing) |  _Support for type hints (see :pep:`484`)._  
|  |   
|  **u** |   
|  [`unicodedata`](https://docs.python.org/3/library/unicodedata.html#module-unicodedata) |  _Access the Unicode Database._  
![-](https://docs.python.org/3/_static/plus.png) |  [`unittest`](https://docs.python.org/3/library/unittest.html#module-unittest) |  _Unit testing framework for Python._  
|  [`unittest.mock`](https://docs.python.org/3/library/unittest.mock.html#module-unittest.mock) |  _Mock object library._  
![-](https://docs.python.org/3/_static/plus.png) |  [`urllib`](https://docs.python.org/3/library/urllib.html#module-urllib) |   
|  [`urllib.error`](https://docs.python.org/3/library/urllib.error.html#module-urllib.error) |  _Exception classes raised by urllib.request._  
|  [`urllib.parse`](https://docs.python.org/3/library/urllib.parse.html#module-urllib.parse) |  _Parse URLs into or assemble them from components._  
|  [`urllib.request`](https://docs.python.org/3/library/urllib.request.html#module-urllib.request) |  _Extensible library for opening URLs._  
|  [`urllib.response`](https://docs.python.org/3/library/urllib.request.html#module-urllib.response) |  _Response classes used by urllib._  
|  [`urllib.robotparser`](https://docs.python.org/3/library/urllib.robotparser.html#module-urllib.robotparser) |  _Load a robots.txt file and answer questions about fetchability of other URLs._  
|  [`usercustomize`](https://docs.python.org/3/library/site.html#module-usercustomize) |   
|  [`uu`](https://docs.python.org/3/library/uu.html#module-uu) |  **Deprecated:** _Removed in 3.13._  
|  [`uuid`](https://docs.python.org/3/library/uuid.html#module-uuid) |  _UUID objects (universally unique identifiers) according to RFC 9562_  
|  |   
|  **v** |   
|  [`venv`](https://docs.python.org/3/library/venv.html#module-venv) |  _Creation of virtual environments._  
|  |   
|  **w** |   
|  [`warnings`](https://docs.python.org/3/library/warnings.html#module-warnings) |  _Issue warning messages and control their disposition._  
|  [`wave`](https://docs.python.org/3/library/wave.html#module-wave) |  _Provide an interface to the WAV sound format._  
|  [`weakref`](https://docs.python.org/3/library/weakref.html#module-weakref) |  _Support for weak references and weak dictionaries._  
|  [`webbrowser`](https://docs.python.org/3/library/webbrowser.html#module-webbrowser) |  _Easy-to-use controller for web browsers._  
|  [`winreg`](https://docs.python.org/3/library/winreg.html#module-winreg) _(Windows)_ |  _Routines and objects for manipulating the Windows registry._  
|  [`winsound`](https://docs.python.org/3/library/winsound.html#module-winsound) _(Windows)_ |  _Access to the sound-playing machinery for Windows._  
![-](https://docs.python.org/3/_static/plus.png) |  [`wsgiref`](https://docs.python.org/3/library/wsgiref.html#module-wsgiref) |  _WSGI Utilities and Reference Implementation._  
|  [`wsgiref.handlers`](https://docs.python.org/3/library/wsgiref.html#module-wsgiref.handlers) |  _WSGI server/gateway base classes._  
|  [`wsgiref.headers`](https://docs.python.org/3/library/wsgiref.html#module-wsgiref.headers) |  _WSGI response header tools._  
|  [`wsgiref.simple_server`](https://docs.python.org/3/library/wsgiref.html#module-wsgiref.simple_server) |  _A simple WSGI HTTP server._  
|  [`wsgiref.types`](https://docs.python.org/3/library/wsgiref.html#module-wsgiref.types) |  _WSGI types for static type checking_  
|  [`wsgiref.util`](https://docs.python.org/3/library/wsgiref.html#module-wsgiref.util) |  _WSGI environment utilities._  
|  [`wsgiref.validate`](https://docs.python.org/3/library/wsgiref.html#module-wsgiref.validate) |  _WSGI conformance checker._  
|  |   
|  **x** |   
|  [`xdrlib`](https://docs.python.org/3/library/xdrlib.html#module-xdrlib) |  **Deprecated:** _Removed in 3.13._  
![-](https://docs.python.org/3/_static/plus.png) |  [`xml`](https://docs.python.org/3/library/xml.html#module-xml) |  _Package containing XML processing modules_  
|  [`xml.dom`](https://docs.python.org/3/library/xml.dom.html#module-xml.dom) |  _Document Object Model API for Python._  
|  [`xml.dom.minidom`](https://docs.python.org/3/library/xml.dom.minidom.html#module-xml.dom.minidom) |  _Minimal Document Object Model (DOM) implementation._  
|  [`xml.dom.pulldom`](https://docs.python.org/3/library/xml.dom.pulldom.html#module-xml.dom.pulldom) |  _Support for building partial DOM trees from SAX events._  
|  [`xml.etree.ElementInclude`](https://docs.python.org/3/library/xml.etree.elementtree.html#module-xml.etree.ElementInclude) |   
|  [`xml.etree.ElementTree`](https://docs.python.org/3/library/xml.etree.elementtree.html#module-xml.etree.ElementTree) |  _Implementation of the ElementTree API._  
|  [`xml.parsers.expat`](https://docs.python.org/3/library/pyexpat.html#module-xml.parsers.expat) |  _An interface to the Expat non-validating XML parser._  
|  [`xml.parsers.expat.errors`](https://docs.python.org/3/library/pyexpat.html#module-xml.parsers.expat.errors) |   
|  [`xml.parsers.expat.model`](https://docs.python.org/3/library/pyexpat.html#module-xml.parsers.expat.model) |   
|  [`xml.sax`](https://docs.python.org/3/library/xml.sax.html#module-xml.sax) |  _Package containing SAX2 base classes and convenience functions._  
|  [`xml.sax.handler`](https://docs.python.org/3/library/xml.sax.handler.html#module-xml.sax.handler) |  _Base classes for SAX event handlers._  
|  [`xml.sax.saxutils`](https://docs.python.org/3/library/xml.sax.utils.html#module-xml.sax.saxutils) |  _Convenience functions and classes for use with SAX._  
|  [`xml.sax.xmlreader`](https://docs.python.org/3/library/xml.sax.reader.html#module-xml.sax.xmlreader) |  _Interface which SAX-compliant XML parsers must implement._  
![-](https://docs.python.org/3/_static/plus.png) |  [`xmlrpc`](https://docs.python.org/3/library/xmlrpc.html#module-xmlrpc) |  _Server and client modules implementing XML-RPC._  
|  [`xmlrpc.client`](https://docs.python.org/3/library/xmlrpc.client.html#module-xmlrpc.client) |  _XML-RPC client access._  
|  [`xmlrpc.server`](https://docs.python.org/3/library/xmlrpc.server.html#module-xmlrpc.server) |  _Basic XML-RPC server implementations._  
|  |   
|  **z** |   
|  [`zipapp`](https://docs.python.org/3/library/zipapp.html#module-zipapp) |  _Manage executable Python zip archives_  
|  [`zipfile`](https://docs.python.org/3/library/zipfile.html#module-zipfile) |  _Read and write ZIP-format archive files._  
|  [`zipimport`](https://docs.python.org/3/library/zipimport.html#module-zipimport) |  _Support for importing Python modules from ZIP archives._  
|  [`zlib`](https://docs.python.org/3/library/zlib.html#module-zlib) |  _Low-level interface to compression and decompression routines compatible with gzip._  
|  [`zoneinfo`](https://docs.python.org/3/library/zoneinfo.html#module-zoneinfo) |  _IANA time zone support_  
«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [Python Module Index](https://docs.python.org/3/py-modindex.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 


---

<!-- SOURCE: https://docs.python.org/3/library/asyncio-stream.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
### [Table of Contents](https://docs.python.org/3/contents.html)
  * [Streams](https://docs.python.org/3/library/asyncio-stream.html)
    * [StreamReader](https://docs.python.org/3/library/asyncio-stream.html#streamreader)
    * [StreamWriter](https://docs.python.org/3/library/asyncio-stream.html#streamwriter)
    * [Examples](https://docs.python.org/3/library/asyncio-stream.html#examples)
      * [TCP echo client using streams](https://docs.python.org/3/library/asyncio-stream.html#tcp-echo-client-using-streams)
      * [TCP echo server using streams](https://docs.python.org/3/library/asyncio-stream.html#tcp-echo-server-using-streams)
      * [Get HTTP headers](https://docs.python.org/3/library/asyncio-stream.html#get-http-headers)
      * [Register an open socket to wait for data using streams](https://docs.python.org/3/library/asyncio-stream.html#register-an-open-socket-to-wait-for-data-using-streams)


#### Previous topic
[Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html "previous chapter")
#### Next topic
[Synchronization Primitives](https://docs.python.org/3/library/asyncio-sync.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio-stream.rst?plain=1)


### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-sync.html "Synchronization Primitives") |
  * [previous](https://docs.python.org/3/library/asyncio-task.html "Coroutines and Tasks") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html) »
  * [Streams](https://docs.python.org/3/library/asyncio-stream.html)
  * | 
  * Theme  Auto Light Dark |


# Streams[¶](https://docs.python.org/3/library/asyncio-stream.html#streams "Link to this heading")
**Source code:** [Lib/asyncio/streams.py](https://github.com/python/cpython/tree/3.14/Lib/asyncio/streams.py)
* * *
Streams are high-level async/await-ready primitives to work with network connections. Streams allow sending and receiving data without using callbacks or low-level protocols and transports.
Here is an example of a TCP echo client written using asyncio streams:
Copy```
import asyncio

async def tcp_echo_client(message):
    reader, writer = await asyncio.open_connection(
        '127.0.0.1', 8888)

    print(f'Send: {message!r}')
    writer.write(message.encode())
    await writer.drain()

    data = await reader.read(100)
    print(f'Received: {data.decode()!r}')

    print('Close the connection')
    writer.close()
    await writer.wait_closed()

asyncio.run(tcp_echo_client('Hello World!'))

```

See also the [Examples](https://docs.python.org/3/library/asyncio-stream.html#examples) section below.
Stream Functions
The following top-level asyncio functions can be used to create and work with streams: 

_async_ asyncio.open_connection(_host =None_, _port =None_, _*_ , _limit =None_, _ssl =None_, _family =0_, _proto =0_, _flags =0_, _sock =None_, _local_addr =None_, _server_hostname =None_, _ssl_handshake_timeout =None_, _ssl_shutdown_timeout =None_, _happy_eyeballs_delay =None_, _interleave =None_)[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.open_connection "Link to this definition") 
    
Establish a network connection and return a pair of `(reader, writer)` objects.
The returned _reader_ and _writer_ objects are instances of [`StreamReader`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader "asyncio.StreamReader") and [`StreamWriter`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter "asyncio.StreamWriter") classes.
_limit_ determines the buffer size limit used by the returned [`StreamReader`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader "asyncio.StreamReader") instance. By default the _limit_ is set to 64 KiB.
The rest of the arguments are passed directly to [`loop.create_connection()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_connection "asyncio.loop.create_connection").
Note
The _sock_ argument transfers ownership of the socket to the [`StreamWriter`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter "asyncio.StreamWriter") created. To close the socket, call its [`close()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.close "asyncio.StreamWriter.close") method.
Changed in version 3.7: Added the _ssl_handshake_timeout_ parameter.
Changed in version 3.8: Added the _happy_eyeballs_delay_ and _interleave_ parameters.
Changed in version 3.10: Removed the _loop_ parameter.
Changed in version 3.11: Added the _ssl_shutdown_timeout_ parameter. 

_async_ asyncio.start_server(_client_connected_cb_ , _host =None_, _port =None_, _*_ , _limit =None_, _family =socket.AF_UNSPEC_, _flags =socket.AI_PASSIVE_, _sock =None_, _backlog =100_, _ssl =None_, _reuse_address =None_, _reuse_port =None_, _keep_alive =None_, _ssl_handshake_timeout =None_, _ssl_shutdown_timeout =None_, _start_serving =True_)[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.start_server "Link to this definition") 
    
Start a socket server.
The _client_connected_cb_ callback is called whenever a new client connection is established. It receives a `(reader, writer)` pair as two arguments, instances of the [`StreamReader`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader "asyncio.StreamReader") and [`StreamWriter`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter "asyncio.StreamWriter") classes.
_client_connected_cb_ can be a plain callable or a [coroutine function](https://docs.python.org/3/library/asyncio-task.html#coroutine); if it is a coroutine function, it will be automatically scheduled as a [`Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task").
_limit_ determines the buffer size limit used by the returned [`StreamReader`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader "asyncio.StreamReader") instance. By default the _limit_ is set to 64 KiB.
The rest of the arguments are passed directly to [`loop.create_server()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_server "asyncio.loop.create_server").
Note
The _sock_ argument transfers ownership of the socket to the server created. To close the socket, call the server’s [`close()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.Server.close "asyncio.Server.close") method.
Changed in version 3.7: Added the _ssl_handshake_timeout_ and _start_serving_ parameters.
Changed in version 3.10: Removed the _loop_ parameter.
Changed in version 3.11: Added the _ssl_shutdown_timeout_ parameter.
Changed in version 3.13: Added the _keep_alive_ parameter.
Unix Sockets 

_async_ asyncio.open_unix_connection(_path =None_, _*_ , _limit =None_, _ssl =None_, _sock =None_, _server_hostname =None_, _ssl_handshake_timeout =None_, _ssl_shutdown_timeout =None_)[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.open_unix_connection "Link to this definition") 
    
Establish a Unix socket connection and return a pair of `(reader, writer)`.
Similar to [`open_connection()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.open_connection "asyncio.open_connection") but operates on Unix sockets.
See also the documentation of [`loop.create_unix_connection()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_unix_connection "asyncio.loop.create_unix_connection").
Note
The _sock_ argument transfers ownership of the socket to the [`StreamWriter`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter "asyncio.StreamWriter") created. To close the socket, call its [`close()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.close "asyncio.StreamWriter.close") method.
[Availability](https://docs.python.org/3/library/intro.html#availability): Unix.
Changed in version 3.7: Added the _ssl_handshake_timeout_ parameter. The _path_ parameter can now be a [path-like object](https://docs.python.org/3/glossary.html#term-path-like-object)
Changed in version 3.10: Removed the _loop_ parameter.
Changed in version 3.11: Added the _ssl_shutdown_timeout_ parameter. 

_async_ asyncio.start_unix_server(_client_connected_cb_ , _path =None_, _*_ , _limit =None_, _sock =None_, _backlog =100_, _ssl =None_, _ssl_handshake_timeout =None_, _ssl_shutdown_timeout =None_, _start_serving =True_, _cleanup_socket =True_)[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.start_unix_server "Link to this definition") 
    
Start a Unix socket server.
Similar to [`start_server()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.start_server "asyncio.start_server") but works with Unix sockets.
If _cleanup_socket_ is true then the Unix socket will automatically be removed from the filesystem when the server is closed, unless the socket has been replaced after the server has been created.
See also the documentation of [`loop.create_unix_server()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_unix_server "asyncio.loop.create_unix_server").
Note
The _sock_ argument transfers ownership of the socket to the server created. To close the socket, call the server’s [`close()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.Server.close "asyncio.Server.close") method.
[Availability](https://docs.python.org/3/library/intro.html#availability): Unix.
Changed in version 3.7: Added the _ssl_handshake_timeout_ and _start_serving_ parameters. The _path_ parameter can now be a [path-like object](https://docs.python.org/3/glossary.html#term-path-like-object).
Changed in version 3.10: Removed the _loop_ parameter.
Changed in version 3.11: Added the _ssl_shutdown_timeout_ parameter.
Changed in version 3.13: Added the _cleanup_socket_ parameter.
## StreamReader[¶](https://docs.python.org/3/library/asyncio-stream.html#streamreader "Link to this heading") 

_class_ asyncio.StreamReader[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader "Link to this definition") 
    
Represents a reader object that provides APIs to read data from the IO stream. As an [asynchronous iterable](https://docs.python.org/3/glossary.html#term-asynchronous-iterable), the object supports the [`async for`](https://docs.python.org/3/reference/compound_stmts.html#async-for) statement.
It is not recommended to instantiate _StreamReader_ objects directly; use [`open_connection()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.open_connection "asyncio.open_connection") and [`start_server()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.start_server "asyncio.start_server") instead. 

feed_eof()[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.feed_eof "Link to this definition") 
    
Acknowledge the EOF. 

_async_ read(_n =-1_)[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.read "Link to this definition") 
    
Read up to _n_ bytes from the stream.
If _n_ is not provided or set to `-1`, read until EOF, then return all read [`bytes`](https://docs.python.org/3/library/stdtypes.html#bytes "bytes"). If EOF was received and the internal buffer is empty, return an empty `bytes` object.
If _n_ is `0`, return an empty `bytes` object immediately.
If _n_ is positive, return at most _n_ available `bytes` as soon as at least 1 byte is available in the internal buffer. If EOF is received before any byte is read, return an empty `bytes` object. 

_async_ readline()[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readline "Link to this definition") 
    
Read one line, where “line” is a sequence of bytes ending with `\n`.
If EOF is received and `\n` was not found, the method returns partially read data.
If EOF is received and the internal buffer is empty, return an empty `bytes` object. 

_async_ readexactly(_n_)[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readexactly "Link to this definition") 
    
Read exactly _n_ bytes.
Raise an [`IncompleteReadError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.IncompleteReadError "asyncio.IncompleteReadError") if EOF is reached before _n_ can be read. Use the [`IncompleteReadError.partial`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.IncompleteReadError.partial "asyncio.IncompleteReadError.partial") attribute to get the partially read data. 

_async_ readuntil(_separator =b'\n'_)[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readuntil "Link to this definition") 
    
Read data from the stream until _separator_ is found.
On success, the data and separator will be removed from the internal buffer (consumed). Returned data will include the separator at the end.
If the amount of data read exceeds the configured stream limit, a [`LimitOverrunError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.LimitOverrunError "asyncio.LimitOverrunError") exception is raised, and the data is left in the internal buffer and can be read again.
If EOF is reached before the complete separator is found, an [`IncompleteReadError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.IncompleteReadError "asyncio.IncompleteReadError") exception is raised, and the internal buffer is reset. The [`IncompleteReadError.partial`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.IncompleteReadError.partial "asyncio.IncompleteReadError.partial") attribute may contain a portion of the separator.
The _separator_ may also be a tuple of separators. In this case the return value will be the shortest possible that has any separator as the suffix. For the purposes of [`LimitOverrunError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.LimitOverrunError "asyncio.LimitOverrunError"), the shortest possible separator is considered to be the one that matched.
Added in version 3.5.2.
Changed in version 3.13: The _separator_ parameter may now be a [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple "tuple") of separators. 

at_eof()[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.at_eof "Link to this definition") 
    
Return `True` if the buffer is empty and [`feed_eof()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.feed_eof "asyncio.StreamReader.feed_eof") was called.
## StreamWriter[¶](https://docs.python.org/3/library/asyncio-stream.html#streamwriter "Link to this heading") 

_class_ asyncio.StreamWriter[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter "Link to this definition") 
    
Represents a writer object that provides APIs to write data to the IO stream.
It is not recommended to instantiate _StreamWriter_ objects directly; use [`open_connection()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.open_connection "asyncio.open_connection") and [`start_server()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.start_server "asyncio.start_server") instead. 

write(_data_)[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.write "Link to this definition") 
    
The method attempts to write the _data_ to the underlying socket immediately. If that fails, the data is queued in an internal write buffer until it can be sent.
The _data_ buffer should be a bytes, bytearray, or C-contiguous one-dimensional memoryview object.
The method should be used along with the `drain()` method:
Copy```
stream.write(data)
await stream.drain()

```


writelines(_data_)[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.writelines "Link to this definition") 
    
The method writes a list (or any iterable) of bytes to the underlying socket immediately. If that fails, the data is queued in an internal write buffer until it can be sent.
The method should be used along with the `drain()` method:
Copy```
stream.writelines(lines)
await stream.drain()

```


close()[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.close "Link to this definition") 
    
The method closes the stream and the underlying socket.
The method should be used, though not mandatory, along with the `wait_closed()` method:
Copy```
stream.close()
await stream.wait_closed()

```


can_write_eof()[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.can_write_eof "Link to this definition") 
    
Return `True` if the underlying transport supports the [`write_eof()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.write_eof "asyncio.StreamWriter.write_eof") method, `False` otherwise. 

write_eof()[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.write_eof "Link to this definition") 
    
Close the write end of the stream after the buffered write data is flushed. 

transport[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.transport "Link to this definition") 
    
Return the underlying asyncio transport. 

get_extra_info(_name_ , _default =None_)[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.get_extra_info "Link to this definition") 
    
Access optional transport information; see [`BaseTransport.get_extra_info()`](https://docs.python.org/3/library/asyncio-protocol.html#asyncio.BaseTransport.get_extra_info "asyncio.BaseTransport.get_extra_info") for details. 

_async_ drain()[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.drain "Link to this definition") 
    
Wait until it is appropriate to resume writing to the stream. Example:
Copy```
writer.write(data)
await writer.drain()

```

This is a flow control method that interacts with the underlying IO write buffer. When the size of the buffer reaches the high watermark, _drain()_ blocks until the size of the buffer is drained down to the low watermark and writing can be resumed. When there is nothing to wait for, the [`drain()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.drain "asyncio.StreamWriter.drain") returns immediately. 

_async_ start_tls(_sslcontext_ , _*_ , _server_hostname =None_, _ssl_handshake_timeout =None_, _ssl_shutdown_timeout =None_)[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.start_tls "Link to this definition") 
    
Upgrade an existing stream-based connection to TLS.
Parameters:
  * _sslcontext_ : a configured instance of [`SSLContext`](https://docs.python.org/3/library/ssl.html#ssl.SSLContext "ssl.SSLContext").
  * _server_hostname_ : sets or overrides the host name that the target server’s certificate will be matched against.
  * _ssl_handshake_timeout_ is the time in seconds to wait for the TLS handshake to complete before aborting the connection. `60.0` seconds if `None` (default).
  * _ssl_shutdown_timeout_ is the time in seconds to wait for the SSL shutdown to complete before aborting the connection. `30.0` seconds if `None` (default).


Added in version 3.11.
Changed in version 3.12: Added the _ssl_shutdown_timeout_ parameter. 

is_closing()[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.is_closing "Link to this definition") 
    
Return `True` if the stream is closed or in the process of being closed.
Added in version 3.7. 

_async_ wait_closed()[¶](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.wait_closed "Link to this definition") 
    
Wait until the stream is closed.
Should be called after [`close()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.close "asyncio.StreamWriter.close") to wait until the underlying connection is closed, ensuring that all data has been flushed before e.g. exiting the program.
Added in version 3.7.
## Examples[¶](https://docs.python.org/3/library/asyncio-stream.html#examples "Link to this heading")
### TCP echo client using streams[¶](https://docs.python.org/3/library/asyncio-stream.html#tcp-echo-client-using-streams "Link to this heading")
TCP echo client using the [`asyncio.open_connection()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.open_connection "asyncio.open_connection") function:
Copy```
import asyncio

async def tcp_echo_client(message):
    reader, writer = await asyncio.open_connection(
        '127.0.0.1', 8888)

    print(f'Send: {message!r}')
    writer.write(message.encode())
    await writer.drain()

    data = await reader.read(100)
    print(f'Received: {data.decode()!r}')

    print('Close the connection')
    writer.close()
    await writer.wait_closed()

asyncio.run(tcp_echo_client('Hello World!'))

```

See also
The [TCP echo client protocol](https://docs.python.org/3/library/asyncio-protocol.html#asyncio-example-tcp-echo-client-protocol) example uses the low-level [`loop.create_connection()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_connection "asyncio.loop.create_connection") method.
### TCP echo server using streams[¶](https://docs.python.org/3/library/asyncio-stream.html#tcp-echo-server-using-streams "Link to this heading")
TCP echo server using the [`asyncio.start_server()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.start_server "asyncio.start_server") function:
Copy```
import asyncio

async def handle_echo(reader, writer):
    data = await reader.read(100)
    message = data.decode()
    addr = writer.get_extra_info('peername')

    print(f"Received {message!r} from {addr!r}")

    print(f"Send: {message!r}")
    writer.write(data)
    await writer.drain()

    print("Close the connection")
    writer.close()
    await writer.wait_closed()

async def main():
    server = await asyncio.start_server(
        handle_echo, '127.0.0.1', 8888)

    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    print(f'Serving on {addrs}')

    async with server:
        await server.serve_forever()

asyncio.run(main())

```

See also
The [TCP echo server protocol](https://docs.python.org/3/library/asyncio-protocol.html#asyncio-example-tcp-echo-server-protocol) example uses the [`loop.create_server()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_server "asyncio.loop.create_server") method.
### Get HTTP headers[¶](https://docs.python.org/3/library/asyncio-stream.html#get-http-headers "Link to this heading")
Simple example querying HTTP headers of the URL passed on the command line:
Copy```
import asyncio
import urllib.parse
import sys

async def print_http_headers(url):
    url = urllib.parse.urlsplit(url)
    if url.scheme == 'https':
        reader, writer = await asyncio.open_connection(
            url.hostname, 443, ssl=True)
    else:
        reader, writer = await asyncio.open_connection(
            url.hostname, 80)

    query = (
        f"HEAD {url.path or '/'} HTTP/1.0\r\n"
        f"Host: {url.hostname}\r\n"
        f"\r\n"
    )

    writer.write(query.encode('latin-1'))
    while True:
        line = await reader.readline()
        if not line:
            break

        line = line.decode('latin1').rstrip()
        if line:
            print(f'HTTP header> {line}')

    # Ignore the body, close the socket
    writer.close()
    await writer.wait_closed()

url = sys.argv[1]
asyncio.run(print_http_headers(url))

```

Usage:
Copy```
python example.py http://example.com/path/page.html

```

or with HTTPS:
Copy```
python example.py https://example.com/path/page.html

```

### Register an open socket to wait for data using streams[¶](https://docs.python.org/3/library/asyncio-stream.html#register-an-open-socket-to-wait-for-data-using-streams "Link to this heading")
Coroutine waiting until a socket receives data using the [`open_connection()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.open_connection "asyncio.open_connection") function:
Copy```
import asyncio
import socket

async def wait_for_data():
    # Get a reference to the current event loop because
    # we want to access low-level APIs.
    loop = asyncio.get_running_loop()

    # Create a pair of connected sockets.
    rsock, wsock = socket.socketpair()

    # Register the open socket to wait for data.
    reader, writer = await asyncio.open_connection(sock=rsock)

    # Simulate the reception of data from the network
    loop.call_soon(wsock.send, 'abc'.encode())

    # Wait for data
    data = await reader.read(100)

    # Got data, we are done: close the socket
    print("Received:", data.decode())
    writer.close()
    await writer.wait_closed()

    # Close the second socket
    wsock.close()

asyncio.run(wait_for_data())

```

See also
The [register an open socket to wait for data using a protocol](https://docs.python.org/3/library/asyncio-protocol.html#asyncio-example-create-connection) example uses a low-level protocol and the [`loop.create_connection()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_connection "asyncio.loop.create_connection") method.
The [watch a file descriptor for read events](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio-example-watch-fd) example uses the low-level [`loop.add_reader()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.add_reader "asyncio.loop.add_reader") method to watch a file descriptor.
### [Table of Contents](https://docs.python.org/3/contents.html)
  * [Streams](https://docs.python.org/3/library/asyncio-stream.html)
    * [StreamReader](https://docs.python.org/3/library/asyncio-stream.html#streamreader)
    * [StreamWriter](https://docs.python.org/3/library/asyncio-stream.html#streamwriter)
    * [Examples](https://docs.python.org/3/library/asyncio-stream.html#examples)
      * [TCP echo client using streams](https://docs.python.org/3/library/asyncio-stream.html#tcp-echo-client-using-streams)
      * [TCP echo server using streams](https://docs.python.org/3/library/asyncio-stream.html#tcp-echo-server-using-streams)
      * [Get HTTP headers](https://docs.python.org/3/library/asyncio-stream.html#get-http-headers)
      * [Register an open socket to wait for data using streams](https://docs.python.org/3/library/asyncio-stream.html#register-an-open-socket-to-wait-for-data-using-streams)


#### Previous topic
[Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html "previous chapter")
#### Next topic
[Synchronization Primitives](https://docs.python.org/3/library/asyncio-sync.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio-stream.rst?plain=1)


«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-sync.html "Synchronization Primitives") |
  * [previous](https://docs.python.org/3/library/asyncio-task.html "Coroutines and Tasks") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html) »
  * [Streams](https://docs.python.org/3/library/asyncio-stream.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 
  *[*]: Keyword-only parameters separator (PEP 3102)


---

<!-- SOURCE: https://docs.python.org/3/library/asyncio-task.html -->
[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
Theme  Auto Light Dark
### [Table of Contents](https://docs.python.org/3/contents.html)
  * [Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html)
    * [Coroutines](https://docs.python.org/3/library/asyncio-task.html#coroutines)
    * [Awaitables](https://docs.python.org/3/library/asyncio-task.html#awaitables)
    * [Creating Tasks](https://docs.python.org/3/library/asyncio-task.html#creating-tasks)
    * [Task Cancellation](https://docs.python.org/3/library/asyncio-task.html#task-cancellation)
    * [Task Groups](https://docs.python.org/3/library/asyncio-task.html#task-groups)
      * [Terminating a Task Group](https://docs.python.org/3/library/asyncio-task.html#terminating-a-task-group)
    * [Sleeping](https://docs.python.org/3/library/asyncio-task.html#sleeping)
    * [Running Tasks Concurrently](https://docs.python.org/3/library/asyncio-task.html#running-tasks-concurrently)
    * [Eager Task Factory](https://docs.python.org/3/library/asyncio-task.html#eager-task-factory)
    * [Shielding From Cancellation](https://docs.python.org/3/library/asyncio-task.html#shielding-from-cancellation)
    * [Timeouts](https://docs.python.org/3/library/asyncio-task.html#timeouts)
    * [Waiting Primitives](https://docs.python.org/3/library/asyncio-task.html#waiting-primitives)
    * [Running in Threads](https://docs.python.org/3/library/asyncio-task.html#running-in-threads)
    * [Scheduling From Other Threads](https://docs.python.org/3/library/asyncio-task.html#scheduling-from-other-threads)
    * [Introspection](https://docs.python.org/3/library/asyncio-task.html#introspection)
    * [Task Object](https://docs.python.org/3/library/asyncio-task.html#task-object)


#### Previous topic
[Runners](https://docs.python.org/3/library/asyncio-runner.html "previous chapter")
#### Next topic
[Streams](https://docs.python.org/3/library/asyncio-stream.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio-task.rst?plain=1)


### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-stream.html "Streams") |
  * [previous](https://docs.python.org/3/library/asyncio-runner.html "Runners") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html) »
  * [Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html)
  * | 
  * Theme  Auto Light Dark |


# Coroutines and Tasks[¶](https://docs.python.org/3/library/asyncio-task.html#coroutines-and-tasks "Link to this heading")
This section outlines high-level asyncio APIs to work with coroutines and Tasks.
  * [Coroutines](https://docs.python.org/3/library/asyncio-task.html#coroutines)
  * [Awaitables](https://docs.python.org/3/library/asyncio-task.html#awaitables)
  * [Creating Tasks](https://docs.python.org/3/library/asyncio-task.html#creating-tasks)
  * [Task Cancellation](https://docs.python.org/3/library/asyncio-task.html#task-cancellation)
  * [Task Groups](https://docs.python.org/3/library/asyncio-task.html#task-groups)
  * [Sleeping](https://docs.python.org/3/library/asyncio-task.html#sleeping)
  * [Running Tasks Concurrently](https://docs.python.org/3/library/asyncio-task.html#running-tasks-concurrently)
  * [Eager Task Factory](https://docs.python.org/3/library/asyncio-task.html#eager-task-factory)
  * [Shielding From Cancellation](https://docs.python.org/3/library/asyncio-task.html#shielding-from-cancellation)
  * [Timeouts](https://docs.python.org/3/library/asyncio-task.html#timeouts)
  * [Waiting Primitives](https://docs.python.org/3/library/asyncio-task.html#waiting-primitives)
  * [Running in Threads](https://docs.python.org/3/library/asyncio-task.html#running-in-threads)
  * [Scheduling From Other Threads](https://docs.python.org/3/library/asyncio-task.html#scheduling-from-other-threads)
  * [Introspection](https://docs.python.org/3/library/asyncio-task.html#introspection)
  * [Task Object](https://docs.python.org/3/library/asyncio-task.html#task-object)


##  [Coroutines](https://docs.python.org/3/library/asyncio-task.html#id2)[¶](https://docs.python.org/3/library/asyncio-task.html#coroutines "Link to this heading")
**Source code:** [Lib/asyncio/coroutines.py](https://github.com/python/cpython/tree/3.14/Lib/asyncio/coroutines.py)
* * *
[Coroutines](https://docs.python.org/3/glossary.html#term-coroutine) declared with the async/await syntax is the preferred way of writing asyncio applications. For example, the following snippet of code prints “hello”, waits 1 second, and then prints “world”:
Copy```
>>> import asyncio

>>> async def main():
...     print('hello')
...     await asyncio.sleep(1)
...     print('world')

>>> asyncio.run(main())
hello
world

```

Note that simply calling a coroutine will not schedule it to be executed:
Copy```
>>> main()
<coroutine object main at 0x1053bb7c8>

```

To actually run a coroutine, asyncio provides the following mechanisms:
  * The [`asyncio.run()`](https://docs.python.org/3/library/asyncio-runner.html#asyncio.run "asyncio.run") function to run the top-level entry point “main()” function (see the above example.)
  * Awaiting on a coroutine. The following snippet of code will print “hello” after waiting for 1 second, and then print “world” after waiting for _another_ 2 seconds:
Copy```
import asyncio
import time

async def say_after(delay, what):
    await asyncio.sleep(delay)
    print(what)

async def main():
    print(f"started at {time.strftime('%X')}")

    await say_after(1, 'hello')
    await say_after(2, 'world')

    print(f"finished at {time.strftime('%X')}")

asyncio.run(main())

```

Expected output:
Copy```
started at 17:13:52
hello
world
finished at 17:13:55

```

  * The [`asyncio.create_task()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task "asyncio.create_task") function to run coroutines concurrently as asyncio [`Tasks`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task").
Let’s modify the above example and run two `say_after` coroutines _concurrently_ :
Copy```
async def main():
    task1 = asyncio.create_task(
        say_after(1, 'hello'))

    task2 = asyncio.create_task(
        say_after(2, 'world'))

    print(f"started at {time.strftime('%X')}")

    # Wait until both tasks are completed (should take
    # around 2 seconds.)
    await task1
    await task2

    print(f"finished at {time.strftime('%X')}")

```

Note that expected output now shows that the snippet runs 1 second faster than before:
Copy```
started at 17:14:32
hello
world
finished at 17:14:34

```

  * The [`asyncio.TaskGroup`](https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup "asyncio.TaskGroup") class provides a more modern alternative to [`create_task()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task "asyncio.create_task"). Using this API, the last example becomes:
Copy```
async def main():
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(
            say_after(1, 'hello'))

        task2 = tg.create_task(
            say_after(2, 'world'))

        print(f"started at {time.strftime('%X')}")

    # The await is implicit when the context manager exits.

    print(f"finished at {time.strftime('%X')}")

```

The timing and output should be the same as for the previous version.
Added in version 3.11: [`asyncio.TaskGroup`](https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup "asyncio.TaskGroup").


##  [Awaitables](https://docs.python.org/3/library/asyncio-task.html#id3)[¶](https://docs.python.org/3/library/asyncio-task.html#awaitables "Link to this heading")
We say that an object is an **awaitable** object if it can be used in an [`await`](https://docs.python.org/3/reference/expressions.html#await) expression. Many asyncio APIs are designed to accept awaitables.
There are three main types of _awaitable_ objects: **coroutines** , **Tasks** , and **Futures**.
Coroutines
Python coroutines are _awaitables_ and therefore can be awaited from other coroutines:
Copy```
import asyncio

async def nested():
    return 42

async def main():
    # Nothing happens if we just call "nested()".
    # A coroutine object is created but not awaited,
    # so it *won't run at all*.
    nested()  # will raise a "RuntimeWarning".

    # Let's do it differently now and await it:
    print(await nested())  # will print "42".

asyncio.run(main())

```

Important
In this documentation the term “coroutine” can be used for two closely related concepts:
  * a _coroutine function_ : an [`async def`](https://docs.python.org/3/reference/compound_stmts.html#async-def) function;
  * a _coroutine object_ : an object returned by calling a _coroutine function_.


Tasks
_Tasks_ are used to schedule coroutines _concurrently_.
When a coroutine is wrapped into a _Task_ with functions like [`asyncio.create_task()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task "asyncio.create_task") the coroutine is automatically scheduled to run soon:
Copy```
import asyncio

async def nested():
    return 42

async def main():
    # Schedule nested() to run soon concurrently
    # with "main()".
    task = asyncio.create_task(nested())

    # "task" can now be used to cancel "nested()", or
    # can simply be awaited to wait until it is complete:
    await task

asyncio.run(main())

```

Futures
A [`Future`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future "asyncio.Future") is a special **low-level** awaitable object that represents an **eventual result** of an asynchronous operation.
When a Future object is _awaited_ it means that the coroutine will wait until the Future is resolved in some other place.
Future objects in asyncio are needed to allow callback-based code to be used with async/await.
Normally **there is no need** to create Future objects at the application level code.
Future objects, sometimes exposed by libraries and some asyncio APIs, can be awaited:
Copy```
async def main():
    await function_that_returns_a_future_object()

    # this is also valid:
    await asyncio.gather(
        function_that_returns_a_future_object(),
        some_python_coroutine()
    )

```

A good example of a low-level function that returns a Future object is [`loop.run_in_executor()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor "asyncio.loop.run_in_executor").
##  [Creating Tasks](https://docs.python.org/3/library/asyncio-task.html#id4)[¶](https://docs.python.org/3/library/asyncio-task.html#creating-tasks "Link to this heading")
**Source code:** [Lib/asyncio/tasks.py](https://github.com/python/cpython/tree/3.14/Lib/asyncio/tasks.py)
* * * 

asyncio.create_task(_coro_ , _*_ , _name =None_, _context =None_, _eager_start =None_, _** kwargs_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task "Link to this definition") 
    
Wrap the _coro_ [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine) into a [`Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task") and schedule its execution. Return the Task object.
The full function signature is largely the same as that of the [`Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task") constructor (or factory) - all of the keyword arguments to this function are passed through to that interface.
An optional keyword-only _context_ argument allows specifying a custom [`contextvars.Context`](https://docs.python.org/3/library/contextvars.html#contextvars.Context "contextvars.Context") for the _coro_ to run in. The current context copy is created when no _context_ is provided.
An optional keyword-only _eager_start_ argument allows specifying if the task should execute eagerly during the call to create_task, or be scheduled later. If _eager_start_ is not passed the mode set by [`loop.set_task_factory()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.set_task_factory "asyncio.loop.set_task_factory") will be used.
The task is executed in the loop returned by [`get_running_loop()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_running_loop "asyncio.get_running_loop"), [`RuntimeError`](https://docs.python.org/3/library/exceptions.html#RuntimeError "RuntimeError") is raised if there is no running loop in current thread.
Note
[`asyncio.TaskGroup.create_task()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup.create_task "asyncio.TaskGroup.create_task") is a new alternative leveraging structural concurrency; it allows for waiting for a group of related tasks with strong safety guarantees.
Important
Save a reference to the result of this function, to avoid a task disappearing mid-execution. The event loop only keeps weak references to tasks. A task that isn’t referenced elsewhere may get garbage collected at any time, even before it’s done. For reliable “fire-and-forget” background tasks, gather them in a collection:
Copy```
background_tasks = set()

for i in range(10):
    task = asyncio.create_task(some_coro(param=i))

    # Add task to the set. This creates a strong reference.
    background_tasks.add(task)

    # To prevent keeping references to finished tasks forever,
    # make each task remove its own reference from the set after
    # completion:
    task.add_done_callback(background_tasks.discard)

```

Added in version 3.7.
Changed in version 3.8: Added the _name_ parameter.
Changed in version 3.11: Added the _context_ parameter.
Changed in version 3.14: Added the _eager_start_ parameter by passing on all _kwargs_.
##  [Task Cancellation](https://docs.python.org/3/library/asyncio-task.html#id5)[¶](https://docs.python.org/3/library/asyncio-task.html#task-cancellation "Link to this heading")
Tasks can easily and safely be cancelled. When a task is cancelled, [`asyncio.CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") will be raised in the task at the next opportunity.
It is recommended that coroutines use `try/finally` blocks to robustly perform clean-up logic. In case [`asyncio.CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") is explicitly caught, it should generally be propagated when clean-up is complete. [`asyncio.CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") directly subclasses [`BaseException`](https://docs.python.org/3/library/exceptions.html#BaseException "BaseException") so most code will not need to be aware of it.
The asyncio components that enable structured concurrency, like [`asyncio.TaskGroup`](https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup "asyncio.TaskGroup") and [`asyncio.timeout()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout "asyncio.timeout"), are implemented using cancellation internally and might misbehave if a coroutine swallows [`asyncio.CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError"). Similarly, user code should not generally call [`uncancel`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.uncancel "asyncio.Task.uncancel"). However, in cases when suppressing [`asyncio.CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") is truly desired, it is necessary to also call `uncancel()` to completely remove the cancellation state.
##  [Task Groups](https://docs.python.org/3/library/asyncio-task.html#id6)[¶](https://docs.python.org/3/library/asyncio-task.html#task-groups "Link to this heading")
Task groups combine a task creation API with a convenient and reliable way to wait for all tasks in the group to finish. 

_class_ asyncio.TaskGroup[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup "Link to this definition") 
    
An [asynchronous context manager](https://docs.python.org/3/reference/datamodel.html#async-context-managers) holding a group of tasks. Tasks can be added to the group using [`create_task()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task "asyncio.create_task"). All tasks are awaited when the context manager exits.
Added in version 3.11. 

create_task(_coro_ , _*_ , _name =None_, _context =None_, _eager_start =None_, _** kwargs_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup.create_task "Link to this definition") 
    
Create a task in this task group. The signature matches that of [`asyncio.create_task()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task "asyncio.create_task"). If the task group is inactive (e.g. not yet entered, already finished, or in the process of shutting down), we will close the given `coro`.
Changed in version 3.13: Close the given coroutine if the task group is not active.
Changed in version 3.14: Passes on all _kwargs_ to [`loop.create_task()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_task "asyncio.loop.create_task")
Example:
Copy```
async def main():
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(some_coro(...))
        task2 = tg.create_task(another_coro(...))
    print(f"Both tasks have completed now: {task1.result()}, {task2.result()}")

```

The `async with` statement will wait for all tasks in the group to finish. While waiting, new tasks may still be added to the group (for example, by passing `tg` into one of the coroutines and calling `tg.create_task()` in that coroutine). Once the last task has finished and the `async with` block is exited, no new tasks may be added to the group.
The first time any of the tasks belonging to the group fails with an exception other than [`asyncio.CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError"), the remaining tasks in the group are cancelled. No further tasks can then be added to the group. At this point, if the body of the `async with` statement is still active (i.e., [`__aexit__()`](https://docs.python.org/3/reference/datamodel.html#object.__aexit__ "object.__aexit__") hasn’t been called yet), the task directly containing the `async with` statement is also cancelled. The resulting [`asyncio.CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") will interrupt an `await`, but it will not bubble out of the containing `async with` statement.
Once all tasks have finished, if any tasks have failed with an exception other than [`asyncio.CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError"), those exceptions are combined in an [`ExceptionGroup`](https://docs.python.org/3/library/exceptions.html#ExceptionGroup "ExceptionGroup") or [`BaseExceptionGroup`](https://docs.python.org/3/library/exceptions.html#BaseExceptionGroup "BaseExceptionGroup") (as appropriate; see their documentation) which is then raised.
Two base exceptions are treated specially: If any task fails with [`KeyboardInterrupt`](https://docs.python.org/3/library/exceptions.html#KeyboardInterrupt "KeyboardInterrupt") or [`SystemExit`](https://docs.python.org/3/library/exceptions.html#SystemExit "SystemExit"), the task group still cancels the remaining tasks and waits for them, but then the initial [`KeyboardInterrupt`](https://docs.python.org/3/library/exceptions.html#KeyboardInterrupt "KeyboardInterrupt") or [`SystemExit`](https://docs.python.org/3/library/exceptions.html#SystemExit "SystemExit") is re-raised instead of [`ExceptionGroup`](https://docs.python.org/3/library/exceptions.html#ExceptionGroup "ExceptionGroup") or [`BaseExceptionGroup`](https://docs.python.org/3/library/exceptions.html#BaseExceptionGroup "BaseExceptionGroup").
If the body of the `async with` statement exits with an exception (so [`__aexit__()`](https://docs.python.org/3/reference/datamodel.html#object.__aexit__ "object.__aexit__") is called with an exception set), this is treated the same as if one of the tasks failed: the remaining tasks are cancelled and then waited for, and non-cancellation exceptions are grouped into an exception group and raised. The exception passed into [`__aexit__()`](https://docs.python.org/3/reference/datamodel.html#object.__aexit__ "object.__aexit__"), unless it is [`asyncio.CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError"), is also included in the exception group. The same special case is made for [`KeyboardInterrupt`](https://docs.python.org/3/library/exceptions.html#KeyboardInterrupt "KeyboardInterrupt") and [`SystemExit`](https://docs.python.org/3/library/exceptions.html#SystemExit "SystemExit") as in the previous paragraph.
Task groups are careful not to mix up the internal cancellation used to “wake up” their [`__aexit__()`](https://docs.python.org/3/reference/datamodel.html#object.__aexit__ "object.__aexit__") with cancellation requests for the task in which they are running made by other parties. In particular, when one task group is syntactically nested in another, and both experience an exception in one of their child tasks simultaneously, the inner task group will process its exceptions, and then the outer task group will receive another cancellation and process its own exceptions.
In the case where a task group is cancelled externally and also must raise an [`ExceptionGroup`](https://docs.python.org/3/library/exceptions.html#ExceptionGroup "ExceptionGroup"), it will call the parent task’s [`cancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel "asyncio.Task.cancel") method. This ensures that a [`asyncio.CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") will be raised at the next [`await`](https://docs.python.org/3/reference/expressions.html#await), so the cancellation is not lost.
Task groups preserve the cancellation count reported by [`asyncio.Task.cancelling()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancelling "asyncio.Task.cancelling").
Changed in version 3.13: Improved handling of simultaneous internal and external cancellations and correct preservation of cancellation counts.
### Terminating a Task Group[¶](https://docs.python.org/3/library/asyncio-task.html#terminating-a-task-group "Link to this heading")
While terminating a task group is not natively supported by the standard library, termination can be achieved by adding an exception-raising task to the task group and ignoring the raised exception:
Copy```
import asyncio
from asyncio import TaskGroup

class TerminateTaskGroup(Exception):
    """Exception raised to terminate a task group."""

async def force_terminate_task_group():
    """Used to force termination of a task group."""
    raise TerminateTaskGroup()

async def job(task_id, sleep_time):
    print(f'Task {task_id}: start')
    await asyncio.sleep(sleep_time)
    print(f'Task {task_id}: done')

async def main():
    try:
        async with TaskGroup() as group:
            # spawn some tasks
            group.create_task(job(1, 0.5))
            group.create_task(job(2, 1.5))
            # sleep for 1 second
            await asyncio.sleep(1)
            # add an exception-raising task to force the group to terminate
            group.create_task(force_terminate_task_group())
    except* TerminateTaskGroup:
        pass

asyncio.run(main())

```

Expected output:
```
Task 1: start
Task 2: start
Task 1: done

```

##  [Sleeping](https://docs.python.org/3/library/asyncio-task.html#id7)[¶](https://docs.python.org/3/library/asyncio-task.html#sleeping "Link to this heading") 

_async_ asyncio.sleep(_delay_ , _result =None_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.sleep "Link to this definition") 
    
Block for _delay_ seconds.
If _result_ is provided, it is returned to the caller when the coroutine completes.
`sleep()` always suspends the current task, allowing other tasks to run.
Setting the delay to 0 provides an optimized path to allow other tasks to run. This can be used by long-running functions to avoid blocking the event loop for the full duration of the function call.
Example of coroutine displaying the current date every second for 5 seconds:
Copy```
import asyncio
import datetime

async def display_date():
    loop = asyncio.get_running_loop()
    end_time = loop.time() + 5.0
    while True:
        print(datetime.datetime.now())
        if (loop.time() + 1.0) >= end_time:
            break
        await asyncio.sleep(1)

asyncio.run(display_date())

```

Changed in version 3.10: Removed the _loop_ parameter.
Changed in version 3.13: Raises [`ValueError`](https://docs.python.org/3/library/exceptions.html#ValueError "ValueError") if _delay_ is [`nan`](https://docs.python.org/3/library/math.html#math.nan "math.nan").
##  [Running Tasks Concurrently](https://docs.python.org/3/library/asyncio-task.html#id8)[¶](https://docs.python.org/3/library/asyncio-task.html#running-tasks-concurrently "Link to this heading") 

_awaitable _asyncio.gather(_* aws_, _return_exceptions =False_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.gather "Link to this definition") 
    
Run [awaitable objects](https://docs.python.org/3/library/asyncio-task.html#asyncio-awaitables) in the _aws_ sequence _concurrently_.
If any awaitable in _aws_ is a coroutine, it is automatically scheduled as a Task.
If all awaitables are completed successfully, the result is an aggregate list of returned values. The order of result values corresponds to the order of awaitables in _aws_.
If _return_exceptions_ is `False` (default), the first raised exception is immediately propagated to the task that awaits on `gather()`. Other awaitables in the _aws_ sequence **won’t be cancelled** and will continue to run.
If _return_exceptions_ is `True`, exceptions are treated the same as successful results, and aggregated in the result list.
If `gather()` is _cancelled_ , all submitted awaitables (that have not completed yet) are also _cancelled_.
If any Task or Future from the _aws_ sequence is _cancelled_ , it is treated as if it raised [`CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") – the `gather()` call is **not** cancelled in this case. This is to prevent the cancellation of one submitted Task/Future to cause other Tasks/Futures to be cancelled.
Note
A new alternative to create and run tasks concurrently and wait for their completion is [`asyncio.TaskGroup`](https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup "asyncio.TaskGroup"). _TaskGroup_ provides stronger safety guarantees than _gather_ for scheduling a nesting of subtasks: if a task (or a subtask, a task scheduled by a task) raises an exception, _TaskGroup_ will, while _gather_ will not, cancel the remaining scheduled tasks).
Example:
Copy```
import asyncio

async def factorial(name, number):
    f = 1
    for i in range(2, number + 1):
        print(f"Task {name}: Compute factorial({number}), currently i={i}...")
        await asyncio.sleep(1)
        f *= i
    print(f"Task {name}: factorial({number}) = {f}")
    return f

async def main():
    # Schedule three calls *concurrently*:
    L = await asyncio.gather(
        factorial("A", 2),
        factorial("B", 3),
        factorial("C", 4),
    )
    print(L)

asyncio.run(main())

# Expected output:
#
#     Task A: Compute factorial(2), currently i=2...
#     Task B: Compute factorial(3), currently i=2...
#     Task C: Compute factorial(4), currently i=2...
#     Task A: factorial(2) = 2
#     Task B: Compute factorial(3), currently i=3...
#     Task C: Compute factorial(4), currently i=3...
#     Task B: factorial(3) = 6
#     Task C: Compute factorial(4), currently i=4...
#     Task C: factorial(4) = 24
#     [2, 6, 24]

```

Note
If _return_exceptions_ is false, cancelling gather() after it has been marked done won’t cancel any submitted awaitables. For instance, gather can be marked done after propagating an exception to the caller, therefore, calling `gather.cancel()` after catching an exception (raised by one of the awaitables) from gather won’t cancel any other awaitables.
Changed in version 3.7: If the _gather_ itself is cancelled, the cancellation is propagated regardless of _return_exceptions_.
Changed in version 3.10: Removed the _loop_ parameter.
Deprecated since version 3.10: Deprecation warning is emitted if no positional arguments are provided or not all positional arguments are Future-like objects and there is no running event loop.
##  [Eager Task Factory](https://docs.python.org/3/library/asyncio-task.html#id9)[¶](https://docs.python.org/3/library/asyncio-task.html#eager-task-factory "Link to this heading") 

asyncio.eager_task_factory(_loop_ , _coro_ , _*_ , _name =None_, _context =None_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.eager_task_factory "Link to this definition") 
    
A task factory for eager task execution.
When using this factory (via [`loop.set_task_factory(asyncio.eager_task_factory)`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.set_task_factory "asyncio.loop.set_task_factory")), coroutines begin execution synchronously during [`Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task") construction. Tasks are only scheduled on the event loop if they block. This can be a performance improvement as the overhead of loop scheduling is avoided for coroutines that complete synchronously.
A common example where this is beneficial is coroutines which employ caching or memoization to avoid actual I/O when possible.
Note
Immediate execution of the coroutine is a semantic change. If the coroutine returns or raises, the task is never scheduled to the event loop. If the coroutine execution blocks, the task is scheduled to the event loop. This change may introduce behavior changes to existing applications. For example, the application’s task execution order is likely to change.
Added in version 3.12. 

asyncio.create_eager_task_factory(_custom_task_constructor_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_eager_task_factory "Link to this definition") 
    
Create an eager task factory, similar to [`eager_task_factory()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.eager_task_factory "asyncio.eager_task_factory"), using the provided _custom_task_constructor_ when creating a new task instead of the default [`Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task").
_custom_task_constructor_ must be a _callable_ with the signature matching the signature of [`Task.__init__`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task"). The callable must return a [`asyncio.Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task")-compatible object.
This function returns a _callable_ intended to be used as a task factory of an event loop via [`loop.set_task_factory(factory)`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.set_task_factory "asyncio.loop.set_task_factory")).
Added in version 3.12.
##  [Shielding From Cancellation](https://docs.python.org/3/library/asyncio-task.html#id10)[¶](https://docs.python.org/3/library/asyncio-task.html#shielding-from-cancellation "Link to this heading") 

_awaitable _asyncio.shield(_aw_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.shield "Link to this definition") 
    
Protect an [awaitable object](https://docs.python.org/3/library/asyncio-task.html#asyncio-awaitables) from being [`cancelled`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel "asyncio.Task.cancel").
If _aw_ is a coroutine it is automatically scheduled as a Task.
The statement:
Copy```
task = asyncio.create_task(something())
res = await shield(task)

```

is equivalent to:
Copy```
res = await something()

```

_except_ that if the coroutine containing it is cancelled, the Task running in `something()` is not cancelled. From the point of view of `something()`, the cancellation did not happen. Although its caller is still cancelled, so the “await” expression still raises a [`CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError").
If `something()` is cancelled by other means (i.e. from within itself) that would also cancel `shield()`.
If it is desired to completely ignore cancellation (not recommended) the `shield()` function should be combined with a try/except clause, as follows:
Copy```
task = asyncio.create_task(something())
try:
    res = await shield(task)
except CancelledError:
    res = None

```

Important
Save a reference to tasks passed to this function, to avoid a task disappearing mid-execution. The event loop only keeps weak references to tasks. A task that isn’t referenced elsewhere may get garbage collected at any time, even before it’s done.
Changed in version 3.10: Removed the _loop_ parameter.
Deprecated since version 3.10: Deprecation warning is emitted if _aw_ is not Future-like object and there is no running event loop.
##  [Timeouts](https://docs.python.org/3/library/asyncio-task.html#id11)[¶](https://docs.python.org/3/library/asyncio-task.html#timeouts "Link to this heading") 

asyncio.timeout(_delay_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout "Link to this definition") 
    
Return an [asynchronous context manager](https://docs.python.org/3/reference/datamodel.html#async-context-managers) that can be used to limit the amount of time spent waiting on something.
_delay_ can either be `None`, or a float/int number of seconds to wait. If _delay_ is `None`, no time limit will be applied; this can be useful if the delay is unknown when the context manager is created.
In either case, the context manager can be rescheduled after creation using [`Timeout.reschedule()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Timeout.reschedule "asyncio.Timeout.reschedule").
Example:
Copy```
async def main():
    async with asyncio.timeout(10):
        await long_running_task()

```

If `long_running_task` takes more than 10 seconds to complete, the context manager will cancel the current task and handle the resulting [`asyncio.CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") internally, transforming it into a [`TimeoutError`](https://docs.python.org/3/library/exceptions.html#TimeoutError "TimeoutError") which can be caught and handled.
Note
The [`asyncio.timeout()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout "asyncio.timeout") context manager is what transforms the [`asyncio.CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") into a [`TimeoutError`](https://docs.python.org/3/library/exceptions.html#TimeoutError "TimeoutError"), which means the [`TimeoutError`](https://docs.python.org/3/library/exceptions.html#TimeoutError "TimeoutError") can only be caught _outside_ of the context manager.
Example of catching [`TimeoutError`](https://docs.python.org/3/library/exceptions.html#TimeoutError "TimeoutError"):
Copy```
async def main():
    try:
        async with asyncio.timeout(10):
            await long_running_task()
    except TimeoutError:
        print("The long operation timed out, but we've handled it.")

    print("This statement will run regardless.")

```

The context manager produced by [`asyncio.timeout()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout "asyncio.timeout") can be rescheduled to a different deadline and inspected. 

_class_ asyncio.Timeout(_when_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Timeout "Link to this definition") 
    
An [asynchronous context manager](https://docs.python.org/3/reference/datamodel.html#async-context-managers) for cancelling overdue coroutines.
Prefer using [`asyncio.timeout()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout "asyncio.timeout") or [`asyncio.timeout_at()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout_at "asyncio.timeout_at") rather than instantiating `Timeout` directly.
`when` should be an absolute time at which the context should time out, as measured by the event loop’s clock:
  * If `when` is `None`, the timeout will never trigger.
  * If `when < loop.time()`, the timeout will trigger on the next iteration of the event loop.


> 

when() → [float](https://docs.python.org/3/library/functions.html#float "float")|[None](https://docs.python.org/3/library/constants.html#None "None")[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Timeout.when "Link to this definition") 
    
> Return the current deadline, or `None` if the current deadline is not set. 

reschedule(_when :[float](https://docs.python.org/3/library/functions.html#float "float")|[None](https://docs.python.org/3/library/constants.html#None "None")_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Timeout.reschedule "Link to this definition") 
    
> Reschedule the timeout. 

expired() → [bool](https://docs.python.org/3/library/functions.html#bool "bool")[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Timeout.expired "Link to this definition") 
    
> Return whether the context manager has exceeded its deadline (expired).
Example:
Copy```
async def main():
    try:
        # We do not know the timeout when starting, so we pass ``None``.
        async with asyncio.timeout(None) as cm:
            # We know the timeout now, so we reschedule it.
            new_deadline = get_running_loop().time() + 10
            cm.reschedule(new_deadline)

            await long_running_task()
    except TimeoutError:
        pass

    if cm.expired():
        print("Looks like we haven't finished on time.")

```

Timeout context managers can be safely nested.
Added in version 3.11. 

asyncio.timeout_at(_when_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout_at "Link to this definition") 
    
Similar to [`asyncio.timeout()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout "asyncio.timeout"), except _when_ is the absolute time to stop waiting, or `None`.
Example:
Copy```
async def main():
    loop = get_running_loop()
    deadline = loop.time() + 20
    try:
        async with asyncio.timeout_at(deadline):
            await long_running_task()
    except TimeoutError:
        print("The long operation timed out, but we've handled it.")

    print("This statement will run regardless.")

```

Added in version 3.11. 

_async_ asyncio.wait_for(_aw_ , _timeout_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for "Link to this definition") 
    
Wait for the _aw_ [awaitable](https://docs.python.org/3/library/asyncio-task.html#asyncio-awaitables) to complete with a timeout.
If _aw_ is a coroutine it is automatically scheduled as a Task.
_timeout_ can either be `None` or a float or int number of seconds to wait for. If _timeout_ is `None`, block until the future completes.
If a timeout occurs, it cancels the task and raises [`TimeoutError`](https://docs.python.org/3/library/exceptions.html#TimeoutError "TimeoutError").
To avoid the task [`cancellation`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel "asyncio.Task.cancel"), wrap it in [`shield()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.shield "asyncio.shield").
The function will wait until the future is actually cancelled, so the total wait time may exceed the _timeout_. If an exception happens during cancellation, it is propagated.
If the wait is cancelled, the future _aw_ is also cancelled.
Example:
Copy```
async def eternity():
    # Sleep for one hour
    await asyncio.sleep(3600)
    print('yay!')

async def main():
    # Wait for at most 1 second
    try:
        await asyncio.wait_for(eternity(), timeout=1.0)
    except TimeoutError:
        print('timeout!')

asyncio.run(main())

# Expected output:
#
#     timeout!

```

Changed in version 3.7: When _aw_ is cancelled due to a timeout, `wait_for` waits for _aw_ to be cancelled. Previously, it raised [`TimeoutError`](https://docs.python.org/3/library/exceptions.html#TimeoutError "TimeoutError") immediately.
Changed in version 3.10: Removed the _loop_ parameter.
Changed in version 3.11: Raises [`TimeoutError`](https://docs.python.org/3/library/exceptions.html#TimeoutError "TimeoutError") instead of [`asyncio.TimeoutError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.TimeoutError "asyncio.TimeoutError").
##  [Waiting Primitives](https://docs.python.org/3/library/asyncio-task.html#id12)[¶](https://docs.python.org/3/library/asyncio-task.html#waiting-primitives "Link to this heading") 

_async_ asyncio.wait(_aws_ , _*_ , _timeout =None_, _return_when =ALL_COMPLETED_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait "Link to this definition") 
    
Run [`Future`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future "asyncio.Future") and [`Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task") instances in the _aws_ iterable concurrently and block until the condition specified by _return_when_.
The _aws_ iterable must not be empty.
Returns two sets of Tasks/Futures: `(done, pending)`.
Usage:
Copy```
done, pending = await asyncio.wait(aws)

```

_timeout_ (a float or int), if specified, can be used to control the maximum number of seconds to wait before returning.
Note that this function does not raise [`TimeoutError`](https://docs.python.org/3/library/exceptions.html#TimeoutError "TimeoutError"). Futures or Tasks that aren’t done when the timeout occurs are simply returned in the second set.
_return_when_ indicates when this function should return. It must be one of the following constants:
Constant | Description  
---|--- 

asyncio.FIRST_COMPLETED[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.FIRST_COMPLETED "Link to this definition") 
| The function will return when any future finishes or is cancelled. 

asyncio.FIRST_EXCEPTION[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.FIRST_EXCEPTION "Link to this definition") 
| The function will return when any future finishes by raising an exception. If no future raises an exception then it is equivalent to [`ALL_COMPLETED`](https://docs.python.org/3/library/asyncio-task.html#asyncio.ALL_COMPLETED "asyncio.ALL_COMPLETED"). 

asyncio.ALL_COMPLETED[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.ALL_COMPLETED "Link to this definition") 
| The function will return when all futures finish or are cancelled.  
Unlike [`wait_for()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for "asyncio.wait_for"), `wait()` does not cancel the futures when a timeout occurs.
Changed in version 3.10: Removed the _loop_ parameter.
Changed in version 3.11: Passing coroutine objects to `wait()` directly is forbidden.
Changed in version 3.12: Added support for generators yielding tasks. 

asyncio.as_completed(_aws_ , _*_ , _timeout =None_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.as_completed "Link to this definition") 
    
Run [awaitable objects](https://docs.python.org/3/library/asyncio-task.html#asyncio-awaitables) in the _aws_ iterable concurrently. The returned object can be iterated to obtain the results of the awaitables as they finish.
The object returned by `as_completed()` can be iterated as an [asynchronous iterator](https://docs.python.org/3/glossary.html#term-asynchronous-iterator) or a plain [iterator](https://docs.python.org/3/glossary.html#term-iterator). When asynchronous iteration is used, the originally-supplied awaitables are yielded if they are tasks or futures. This makes it easy to correlate previously-scheduled tasks with their results. Example:
Copy```
ipv4_connect = create_task(open_connection("127.0.0.1", 80))
ipv6_connect = create_task(open_connection("::1", 80))
tasks = [ipv4_connect, ipv6_connect]

async for earliest_connect in as_completed(tasks):
    # earliest_connect is done. The result can be obtained by
    # awaiting it or calling earliest_connect.result()
    reader, writer = await earliest_connect

    if earliest_connect is ipv6_connect:
        print("IPv6 connection established.")
    else:
        print("IPv4 connection established.")

```

During asynchronous iteration, implicitly-created tasks will be yielded for supplied awaitables that aren’t tasks or futures.
When used as a plain iterator, each iteration yields a new coroutine that returns the result or raises the exception of the next completed awaitable. This pattern is compatible with Python versions older than 3.13:
Copy```
ipv4_connect = create_task(open_connection("127.0.0.1", 80))
ipv6_connect = create_task(open_connection("::1", 80))
tasks = [ipv4_connect, ipv6_connect]

for next_connect in as_completed(tasks):
    # next_connect is not one of the original task objects. It must be
    # awaited to obtain the result value or raise the exception of the
    # awaitable that finishes next.
    reader, writer = await next_connect

```

A [`TimeoutError`](https://docs.python.org/3/library/exceptions.html#TimeoutError "TimeoutError") is raised if the timeout occurs before all awaitables are done. This is raised by the `async for` loop during asynchronous iteration or by the coroutines yielded during plain iteration.
Changed in version 3.10: Removed the _loop_ parameter.
Deprecated since version 3.10: Deprecation warning is emitted if not all awaitable objects in the _aws_ iterable are Future-like objects and there is no running event loop.
Changed in version 3.12: Added support for generators yielding tasks.
Changed in version 3.13: The result can now be used as either an [asynchronous iterator](https://docs.python.org/3/glossary.html#term-asynchronous-iterator) or as a plain [iterator](https://docs.python.org/3/glossary.html#term-iterator) (previously it was only a plain iterator).
##  [Running in Threads](https://docs.python.org/3/library/asyncio-task.html#id13)[¶](https://docs.python.org/3/library/asyncio-task.html#running-in-threads "Link to this heading") 

_async_ asyncio.to_thread(_func_ , _/_ , _* args_, _** kwargs_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread "Link to this definition") 
    
Asynchronously run function _func_ in a separate thread.
Any *args and **kwargs supplied for this function are directly passed to _func_. Also, the current [`contextvars.Context`](https://docs.python.org/3/library/contextvars.html#contextvars.Context "contextvars.Context") is propagated, allowing context variables from the event loop thread to be accessed in the separate thread.
Return a coroutine that can be awaited to get the eventual result of _func_.
This coroutine function is primarily intended to be used for executing IO-bound functions/methods that would otherwise block the event loop if they were run in the main thread. For example:
Copy```
def blocking_io():
    print(f"start blocking_io at {time.strftime('%X')}")
    # Note that time.sleep() can be replaced with any blocking
    # IO-bound operation, such as file operations.
    time.sleep(1)
    print(f"blocking_io complete at {time.strftime('%X')}")

async def main():
    print(f"started main at {time.strftime('%X')}")

    await asyncio.gather(
        asyncio.to_thread(blocking_io),
        asyncio.sleep(1))

    print(f"finished main at {time.strftime('%X')}")


asyncio.run(main())

# Expected output:
#
# started main at 19:50:53
# start blocking_io at 19:50:53
# blocking_io complete at 19:50:54
# finished main at 19:50:54

```

Directly calling `blocking_io()` in any coroutine would block the event loop for its duration, resulting in an additional 1 second of run time. Instead, by using `asyncio.to_thread()`, we can run it in a separate thread without blocking the event loop.
Note
Due to the [GIL](https://docs.python.org/3/glossary.html#term-GIL), `asyncio.to_thread()` can typically only be used to make IO-bound functions non-blocking. However, for extension modules that release the GIL or alternative Python implementations that don’t have one, `asyncio.to_thread()` can also be used for CPU-bound functions.
Added in version 3.9.
##  [Scheduling From Other Threads](https://docs.python.org/3/library/asyncio-task.html#id14)[¶](https://docs.python.org/3/library/asyncio-task.html#scheduling-from-other-threads "Link to this heading") 

asyncio.run_coroutine_threadsafe(_coro_ , _loop_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.run_coroutine_threadsafe "Link to this definition") 
    
Submit a coroutine to the given event loop. Thread-safe.
Return a [`concurrent.futures.Future`](https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future "concurrent.futures.Future") to wait for the result from another OS thread.
This function is meant to be called from a different OS thread than the one where the event loop is running. Example:
Copy```
def in_thread(loop: asyncio.AbstractEventLoop) -> None:
    # Run some blocking IO
    pathlib.Path("example.txt").write_text("hello world", encoding="utf8")

    # Create a coroutine
    coro = asyncio.sleep(1, result=3)

    # Submit the coroutine to a given loop
    future = asyncio.run_coroutine_threadsafe(coro, loop)

    # Wait for the result with an optional timeout argument
    assert future.result(timeout=2) == 3

async def amain() -> None:
    # Get the running loop
    loop = asyncio.get_running_loop()

    # Run something in a thread
    await asyncio.to_thread(in_thread, loop)

```

It’s also possible to run the other way around. Example:
Copy```
@contextlib.contextmanager
def loop_in_thread() -> Generator[asyncio.AbstractEventLoop]:
    loop_fut = concurrent.futures.Future[asyncio.AbstractEventLoop]()
    stop_event = asyncio.Event()

    async def main() -> None:
        loop_fut.set_result(asyncio.get_running_loop())
        await stop_event.wait()

    with concurrent.futures.ThreadPoolExecutor(1) as tpe:
        complete_fut = tpe.submit(asyncio.run, main())
        for fut in concurrent.futures.as_completed((loop_fut, complete_fut)):
            if fut is loop_fut:
                loop = loop_fut.result()
                try:
                    yield loop
                finally:
                    loop.call_soon_threadsafe(stop_event.set)
            else:
                fut.result()

# Create a loop in another thread
with loop_in_thread() as loop:
    # Create a coroutine
    coro = asyncio.sleep(1, result=3)

    # Submit the coroutine to a given loop
    future = asyncio.run_coroutine_threadsafe(coro, loop)

    # Wait for the result with an optional timeout argument
    assert future.result(timeout=2) == 3

```

If an exception is raised in the coroutine, the returned Future will be notified. It can also be used to cancel the task in the event loop:
Copy```
try:
    result = future.result(timeout)
except TimeoutError:
    print('The coroutine took too long, cancelling the task...')
    future.cancel()
except Exception as exc:
    print(f'The coroutine raised an exception: {exc!r}')
else:
    print(f'The coroutine returned: {result!r}')

```

See the [concurrency and multithreading](https://docs.python.org/3/library/asyncio-dev.html#asyncio-multithreading) section of the documentation.
Unlike other asyncio functions this function requires the _loop_ argument to be passed explicitly.
Added in version 3.5.1.
##  [Introspection](https://docs.python.org/3/library/asyncio-task.html#id15)[¶](https://docs.python.org/3/library/asyncio-task.html#introspection "Link to this heading") 

asyncio.current_task(_loop =None_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.current_task "Link to this definition") 
    
Return the currently running [`Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task") instance, or `None` if no task is running.
If _loop_ is `None` [`get_running_loop()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_running_loop "asyncio.get_running_loop") is used to get the current loop.
Added in version 3.7. 

asyncio.all_tasks(_loop =None_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.all_tasks "Link to this definition") 
    
Return a set of not yet finished [`Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task") objects run by the loop.
If _loop_ is `None`, [`get_running_loop()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_running_loop "asyncio.get_running_loop") is used for getting current loop.
Added in version 3.7. 

asyncio.iscoroutine(_obj_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.iscoroutine "Link to this definition") 
    
Return `True` if _obj_ is a coroutine object.
Added in version 3.4.
##  [Task Object](https://docs.python.org/3/library/asyncio-task.html#id16)[¶](https://docs.python.org/3/library/asyncio-task.html#task-object "Link to this heading") 

_class_ asyncio.Task(_coro_ , _*_ , _loop =None_, _name =None_, _context =None_, _eager_start =False_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "Link to this definition") 
    
A [`Future-like`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future "asyncio.Future") object that runs a Python [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine). Not thread-safe.
Tasks are used to run coroutines in event loops. If a coroutine awaits on a Future, the Task suspends the execution of the coroutine and waits for the completion of the Future. When the Future is _done_ , the execution of the wrapped coroutine resumes.
Event loops use cooperative scheduling: an event loop runs one Task at a time. While a Task awaits for the completion of a Future, the event loop runs other Tasks, callbacks, or performs IO operations.
Use the high-level [`asyncio.create_task()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task "asyncio.create_task") function to create Tasks, or the low-level [`loop.create_task()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_task "asyncio.loop.create_task") or [`ensure_future()`](https://docs.python.org/3/library/asyncio-future.html#asyncio.ensure_future "asyncio.ensure_future") functions. Manual instantiation of Tasks is discouraged.
To cancel a running Task use the [`cancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel "asyncio.Task.cancel") method. Calling it will cause the Task to throw a [`CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") exception into the wrapped coroutine. If a coroutine is awaiting on a Future object during cancellation, the Future object will be cancelled.
[`cancelled()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancelled "asyncio.Task.cancelled") can be used to check if the Task was cancelled. The method returns `True` if the wrapped coroutine did not suppress the [`CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") exception and was actually cancelled.
[`asyncio.Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task") inherits from [`Future`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future "asyncio.Future") all of its APIs except [`Future.set_result()`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.set_result "asyncio.Future.set_result") and [`Future.set_exception()`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.set_exception "asyncio.Future.set_exception").
An optional keyword-only _context_ argument allows specifying a custom [`contextvars.Context`](https://docs.python.org/3/library/contextvars.html#contextvars.Context "contextvars.Context") for the _coro_ to run in. If no _context_ is provided, the Task copies the current context and later runs its coroutine in the copied context.
An optional keyword-only _eager_start_ argument allows eagerly starting the execution of the [`asyncio.Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task") at task creation time. If set to `True` and the event loop is running, the task will start executing the coroutine immediately, until the first time the coroutine blocks. If the coroutine returns or raises without blocking, the task will be finished eagerly and will skip scheduling to the event loop.
Changed in version 3.7: Added support for the [`contextvars`](https://docs.python.org/3/library/contextvars.html#module-contextvars "contextvars: Context Variables") module.
Changed in version 3.8: Added the _name_ parameter.
Deprecated since version 3.10: Deprecation warning is emitted if _loop_ is not specified and there is no running event loop.
Changed in version 3.11: Added the _context_ parameter.
Changed in version 3.12: Added the _eager_start_ parameter. 

done()[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.done "Link to this definition") 
    
Return `True` if the Task is _done_.
A Task is _done_ when the wrapped coroutine either returned a value, raised an exception, or the Task was cancelled. 

result()[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.result "Link to this definition") 
    
Return the result of the Task.
If the Task is _done_ , the result of the wrapped coroutine is returned (or if the coroutine raised an exception, that exception is re-raised.)
If the Task has been _cancelled_ , this method raises a [`CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") exception.
If the Task’s result isn’t yet available, this method raises an [`InvalidStateError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.InvalidStateError "asyncio.InvalidStateError") exception. 

exception()[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.exception "Link to this definition") 
    
Return the exception of the Task.
If the wrapped coroutine raised an exception that exception is returned. If the wrapped coroutine returned normally this method returns `None`.
If the Task has been _cancelled_ , this method raises a [`CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") exception.
If the Task isn’t _done_ yet, this method raises an [`InvalidStateError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.InvalidStateError "asyncio.InvalidStateError") exception. 

add_done_callback(_callback_ , _*_ , _context =None_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.add_done_callback "Link to this definition") 
    
Add a callback to be run when the Task is _done_.
This method should only be used in low-level callback-based code.
See the documentation of [`Future.add_done_callback()`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.add_done_callback "asyncio.Future.add_done_callback") for more details. 

remove_done_callback(_callback_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.remove_done_callback "Link to this definition") 
    
Remove _callback_ from the callbacks list.
This method should only be used in low-level callback-based code.
See the documentation of [`Future.remove_done_callback()`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.remove_done_callback "asyncio.Future.remove_done_callback") for more details. 

get_stack(_*_ , _limit =None_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.get_stack "Link to this definition") 
    
Return the list of stack frames for this Task.
If the wrapped coroutine is not done, this returns the stack where it is suspended. If the coroutine has completed successfully or was cancelled, this returns an empty list. If the coroutine was terminated by an exception, this returns the list of traceback frames.
The frames are always ordered from oldest to newest.
Only one stack frame is returned for a suspended coroutine.
The optional _limit_ argument sets the maximum number of frames to return; by default all available frames are returned. The ordering of the returned list differs depending on whether a stack or a traceback is returned: the newest frames of a stack are returned, but the oldest frames of a traceback are returned. (This matches the behavior of the traceback module.) 

print_stack(_*_ , _limit =None_, _file =None_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.print_stack "Link to this definition") 
    
Print the stack or traceback for this Task.
This produces output similar to that of the traceback module for the frames retrieved by [`get_stack()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.get_stack "asyncio.Task.get_stack").
The _limit_ argument is passed to [`get_stack()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.get_stack "asyncio.Task.get_stack") directly.
The _file_ argument is an I/O stream to which the output is written; by default output is written to [`sys.stdout`](https://docs.python.org/3/library/sys.html#sys.stdout "sys.stdout"). 

get_coro()[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.get_coro "Link to this definition") 
    
Return the coroutine object wrapped by the [`Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task "asyncio.Task").
Note
This will return `None` for Tasks which have already completed eagerly. See the [Eager Task Factory](https://docs.python.org/3/library/asyncio-task.html#eager-task-factory).
Added in version 3.8.
Changed in version 3.12: Newly added eager task execution means result may be `None`. 

get_context()[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.get_context "Link to this definition") 
    
Return the [`contextvars.Context`](https://docs.python.org/3/library/contextvars.html#contextvars.Context "contextvars.Context") object associated with the task.
Added in version 3.12. 

get_name()[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.get_name "Link to this definition") 
    
Return the name of the Task.
If no name has been explicitly assigned to the Task, the default asyncio Task implementation generates a default name during instantiation.
Added in version 3.8. 

set_name(_value_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.set_name "Link to this definition") 
    
Set the name of the Task.
The _value_ argument can be any object, which is then converted to a string.
In the default Task implementation, the name will be visible in the [`repr()`](https://docs.python.org/3/library/functions.html#repr "repr") output of a task object.
Added in version 3.8. 

cancel(_msg =None_)[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel "Link to this definition") 
    
Request the Task to be cancelled.
If the Task is already _done_ or _cancelled_ , return `False`, otherwise, return `True`.
The method arranges for a [`CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") exception to be thrown into the wrapped coroutine on the next cycle of the event loop.
The coroutine then has a chance to clean up or even deny the request by suppressing the exception with a [`try`](https://docs.python.org/3/reference/compound_stmts.html#try) … … `except CancelledError` … [`finally`](https://docs.python.org/3/reference/compound_stmts.html#finally) block. Therefore, unlike [`Future.cancel()`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.cancel "asyncio.Future.cancel"), [`Task.cancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel "asyncio.Task.cancel") does not guarantee that the Task will be cancelled, although suppressing cancellation completely is not common and is actively discouraged. Should the coroutine nevertheless decide to suppress the cancellation, it needs to call [`Task.uncancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.uncancel "asyncio.Task.uncancel") in addition to catching the exception.
Changed in version 3.9: Added the _msg_ parameter.
Changed in version 3.11: The `msg` parameter is propagated from cancelled task to its awaiter.
The following example illustrates how coroutines can intercept the cancellation request:
Copy```
async def cancel_me():
    print('cancel_me(): before sleep')

    try:
        # Wait for 1 hour
        await asyncio.sleep(3600)
    except asyncio.CancelledError:
        print('cancel_me(): cancel sleep')
        raise
    finally:
        print('cancel_me(): after sleep')

async def main():
    # Create a "cancel_me" Task
    task = asyncio.create_task(cancel_me())

    # Wait for 1 second
    await asyncio.sleep(1)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("main(): cancel_me is cancelled now")

asyncio.run(main())

# Expected output:
#
#     cancel_me(): before sleep
#     cancel_me(): cancel sleep
#     cancel_me(): after sleep
#     main(): cancel_me is cancelled now

```


cancelled()[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancelled "Link to this definition") 
    
Return `True` if the Task is _cancelled_.
The Task is _cancelled_ when the cancellation was requested with [`cancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel "asyncio.Task.cancel") and the wrapped coroutine propagated the [`CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") exception thrown into it. 

uncancel()[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.uncancel "Link to this definition") 
    
Decrement the count of cancellation requests to this Task.
Returns the remaining number of cancellation requests.
Note that once execution of a cancelled task completed, further calls to [`uncancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.uncancel "asyncio.Task.uncancel") are ineffective.
Added in version 3.11.
This method is used by asyncio’s internals and isn’t expected to be used by end-user code. In particular, if a Task gets successfully uncancelled, this allows for elements of structured concurrency like [Task Groups](https://docs.python.org/3/library/asyncio-task.html#taskgroups) and [`asyncio.timeout()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout "asyncio.timeout") to continue running, isolating cancellation to the respective structured block. For example:
Copy```
async def make_request_with_timeout():
    try:
        async with asyncio.timeout(1):
            # Structured block affected by the timeout:
            await make_request()
            await make_another_request()
    except TimeoutError:
        log("There was a timeout")
    # Outer code not affected by the timeout:
    await unrelated_code()

```

While the block with `make_request()` and `make_another_request()` might get cancelled due to the timeout, `unrelated_code()` should continue running even in case of the timeout. This is implemented with [`uncancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.uncancel "asyncio.Task.uncancel"). [`TaskGroup`](https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup "asyncio.TaskGroup") context managers use [`uncancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.uncancel "asyncio.Task.uncancel") in a similar fashion.
If end-user code is, for some reason, suppressing cancellation by catching [`CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError"), it needs to call this method to remove the cancellation state.
When this method decrements the cancellation count to zero, the method checks if a previous [`cancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel "asyncio.Task.cancel") call had arranged for [`CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError "asyncio.CancelledError") to be thrown into the task. If it hasn’t been thrown yet, that arrangement will be rescinded (by resetting the internal `_must_cancel` flag).
Changed in version 3.13: Changed to rescind pending cancellation requests upon reaching zero. 

cancelling()[¶](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancelling "Link to this definition") 
    
Return the number of pending cancellation requests to this Task, i.e., the number of calls to [`cancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel "asyncio.Task.cancel") less the number of [`uncancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.uncancel "asyncio.Task.uncancel") calls.
Note that if this number is greater than zero but the Task is still executing, [`cancelled()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancelled "asyncio.Task.cancelled") will still return `False`. This is because this number can be lowered by calling [`uncancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.uncancel "asyncio.Task.uncancel"), which can lead to the task not being cancelled after all if the cancellation requests go down to zero.
This method is used by asyncio’s internals and isn’t expected to be used by end-user code. See [`uncancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.uncancel "asyncio.Task.uncancel") for more details.
Added in version 3.11.
### [Table of Contents](https://docs.python.org/3/contents.html)
  * [Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html)
    * [Coroutines](https://docs.python.org/3/library/asyncio-task.html#coroutines)
    * [Awaitables](https://docs.python.org/3/library/asyncio-task.html#awaitables)
    * [Creating Tasks](https://docs.python.org/3/library/asyncio-task.html#creating-tasks)
    * [Task Cancellation](https://docs.python.org/3/library/asyncio-task.html#task-cancellation)
    * [Task Groups](https://docs.python.org/3/library/asyncio-task.html#task-groups)
      * [Terminating a Task Group](https://docs.python.org/3/library/asyncio-task.html#terminating-a-task-group)
    * [Sleeping](https://docs.python.org/3/library/asyncio-task.html#sleeping)
    * [Running Tasks Concurrently](https://docs.python.org/3/library/asyncio-task.html#running-tasks-concurrently)
    * [Eager Task Factory](https://docs.python.org/3/library/asyncio-task.html#eager-task-factory)
    * [Shielding From Cancellation](https://docs.python.org/3/library/asyncio-task.html#shielding-from-cancellation)
    * [Timeouts](https://docs.python.org/3/library/asyncio-task.html#timeouts)
    * [Waiting Primitives](https://docs.python.org/3/library/asyncio-task.html#waiting-primitives)
    * [Running in Threads](https://docs.python.org/3/library/asyncio-task.html#running-in-threads)
    * [Scheduling From Other Threads](https://docs.python.org/3/library/asyncio-task.html#scheduling-from-other-threads)
    * [Introspection](https://docs.python.org/3/library/asyncio-task.html#introspection)
    * [Task Object](https://docs.python.org/3/library/asyncio-task.html#task-object)


#### Previous topic
[Runners](https://docs.python.org/3/library/asyncio-runner.html "previous chapter")
#### Next topic
[Streams](https://docs.python.org/3/library/asyncio-stream.html "next chapter")
### This page
  * [Report a bug](https://docs.python.org/3/bugs.html)
  * [Show source ](https://github.com/python/cpython/blob/main/Doc/library/asyncio-task.rst?plain=1)


«
### Navigation
  * [index](https://docs.python.org/3/genindex.html "General Index")
  * [modules](https://docs.python.org/3/py-modindex.html "Python Module Index") |
  * [next](https://docs.python.org/3/library/asyncio-stream.html "Streams") |
  * [previous](https://docs.python.org/3/library/asyncio-runner.html "Runners") |
  * ![Python logo](https://docs.python.org/3/_static/py.svg)
  * [Python](https://www.python.org/) »
  * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文
dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6
  * [3.14.3 Documentation](https://docs.python.org/3/index.html) » 
  * [The Python Standard Library](https://docs.python.org/3/library/index.html) »
  * [Networking and Interprocess Communication](https://docs.python.org/3/library/ipc.html) »
  * [`asyncio` — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html) »
  * [Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html)
  * | 
  * Theme  Auto Light Dark |


© [Copyright](https://docs.python.org/3/copyright.html) 2001 Python Software Foundation.   
This page is licensed under the Python Software Foundation License Version 2.   
Examples, recipes, and other code in the documentation are additionally licensed under the Zero Clause BSD License.   
See [History and License](https://docs.python.org/license.html) for more information.  
  
The Python Software Foundation is a non-profit corporation. [Please donate.](https://www.python.org/psf/donations/)   
  
Last updated on Feb 07, 2026 (22:44 UTC). [Found a bug](https://docs.python.org/bugs.html)?   
Created using [Sphinx](https://www.sphinx-doc.org/) 8.2.3. 
  *[*]: Keyword-only parameters separator (PEP 3102)
  *[/]: Positional-only parameter separator (PEP 570)


---


