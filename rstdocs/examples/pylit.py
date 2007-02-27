#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# ===============================================================
# pylit.py: Literate programming with Python and reStructuredText
# ===============================================================
# 
# :Date:      2007-01-31
# :Copyright: 2005, 2007 Guenter Milde.
#             Released under the terms of the GNU General Public License 
#             (v. 2 or later)
# 
# .. sectnum::
# .. contents::
# 
# Frontmatter
# ===========
# 
# Changelog
# ---------
# 
# :2005-06-29: Initial version
# :2005-06-30: first literate version of the script
# :2005-07-01: object orientated script using generators
# :2005-07-10: Two state machine (later added 'header' state)
# :2006-12-04: Start of work on version 0.2 (code restructuring)
# :2007-01-23: 0.2   published at http://pylit.berlios.de
# :2007-01-25: 0.2.1 Outsourced non-core documentation to the PyLit pages.
# :2007-01-26: 0.2.2 new behaviour of `diff` function
# :2007-01-29: 0.2.3 new `header` methods after suggestion by Riccardo Murri
# :2007-01-31: 0.2.4 raise Error if code indent is too small
# :2007-02-05: 0.2.5 new command line option --comment-string
# :2007-02-09: 0.2.6 add section with open questions,
#                    Code2Text: let only blank lines (no comment str)
#                    separate text and code,
#                    fix `Code2Text.header`
# :2007-02-19: 0.2.7 simplify `Code2Text.header,`
#                    new `iter_strip` method replacing a lot of ``if``-s
# :2007-02-22: 0.2.8 set `mtime` of outfile to the one of infile
#                    customization doc for `main`
# 
# ::

"""pylit: Literate programming with Python and reStructuredText
   
   PyLit is a bidirectional converter between
   
   * a (reStructured) text source with embedded code, and
   * a code source with embedded text blocks (comments)
"""

__docformat__ = 'restructuredtext'


# Requirements
# ------------
# 
# * library modules
# 
# ::

import os
import sys
import optparse

# * non-standard extensions
# 
# ::

from simplestates import SimpleStates  # generic state machine

 
# Classes
# =======
# 
# PushIterator
# ------------
# 
# The PushIterator is a minimal implementation of an iterator with
# backtracking from the `Effective Python Programming`_ OSCON 2005 tutorial by
# Anthony�Baxter. As the definition is small, it is inlined now. For the full
# reasoning and documentation see `iterqueue.py`_.
# 
# .. _`Effective Python Programming`: 
#    http://www.interlink.com.au/anthony/tech/talks/OSCON2005/effective_r27.pdf
# 
# .. _iterqueue.py: iterqueue.py.html
# 
# ::

class PushIterator:
    def __init__(self, iterable):
        self.it = iter(iterable)
        self.cache = []
    def __iter__(self):
        """Return `self`, as this is already an iterator"""
        return self
    def next(self):
        return (self.cache and self.cache.pop()) or self.it.next()
    def push(self, value):
        self.cache.append(value)

# Converter
# ---------
# 
# The converter classes implement a simple `state machine` to separate and
# transform text and code blocks. For this task, only a very limited parsing
# is needed.  Using the full blown docutils_ rst parser would introduce a
# large overhead and slow down the conversion. 
# 
# PyLit's simple parser assumes:
# 
# * indented literal blocks in a text source are code blocks.
# 
# * comment lines that start with a matching comment string in a code source
#   are text blocks.
# 
# .. _docutils: http://docutils.sourceforge.net/
# 
# The actual converter classes are derived from `PyLitConverter`: 
# `Text2Code`_ converts a text source to executable code, while `Code2Text`_
# does the opposite: converting commented code to a text source.
# 
# The `PyLitConverter` class inherits the state machine framework
# (initalisation, scheduler, iterator interface, ...) from `SimpleStates`,
# overrides the ``__init__`` method, and adds auxiliary methods and
# configuration attributes (options). ::

class PyLitConverter(SimpleStates):
    """parent class for `Text2Code` and `Code2Text`, the state machines
    converting between text source and code source of a literal program.
    """

# Data attributes
# ~~~~~~~~~~~~~~~
# 
# The data attributes are class default values. They will be overridden by
# matching keyword arguments during class instantiation.
# 
# `get_converter`_ and `main`_ pass on unused keyword arguments to
# the instantiation of a converter class. This way, keyword arguments
# to these functions can be used to customize the converter. 

# Default language and language specific defaults::

    language =        "python"        
    comment_strings = {"python": '# ',
                       "slang": '% ', 
                       "c++": '// '}  

# Number of spaces to indent code blocks in the code -> text conversion.[#]_
# 
# .. [#] For the text -> code conversion, the codeindent is determined by the
#        first recognized code line (leading comment or first indented literal
#        block of the text source).
# 
# ::

    codeindent =  2

# Marker string for the first code block. (Should be a valid rst directive
# that accepts code on the same line, e.g. ``'.. admonition::'``.)  No
# trailing whitespace needed as indented code follows. Default is a comment
# marker::

    header_string = '..'

# Export to the output format stripping text or code blocks::

    strip =           False
    
# Initial state::

    state = 'header' 


# Instantiation
# ~~~~~~~~~~~~~
# 
# Initializing sets up the `data` attribute, an iterable object yielding
# lines of the source to convert.[1]_   ::

    def __init__(self, data, **keyw):
        """data   --  iterable data object 
                      (list, file, generator, string, ...)
           **keyw --  all remaining keyword arguments are 
                      stored as class attributes 
        """

# As the state handlers need backtracking, the data is wrapped in a
# `PushIterator`_ if it doesnot already have a `push` method::

        if hasattr(data, 'push'):
            self.data = data
        else:
            self.data = PushIterator(data)
        self._textindent = 0

# Additional keyword arguments are stored as data attributes, overwriting the
# class defaults::

        self.__dict__.update(keyw)
            
# The comment string is set to the languages comment string if not given in
# the keyword arguments::

        if not hasattr(self, "comment_string") or not self.comment_string:
            self.comment_string = self.comment_strings[self.language]
            
# If the `strip` argument is true, replace the `__iter_` method
# with a special one that drops "spurious" blocks::

        if getattr(self, "strip", False):
            self.__iter__ = self.iter_strip

# .. [1] The most common choice of data is a `file` object with the text
#        or code source.
# 
#        To convert a string into a suitable object, use its splitlines method
#        with the optional `keepends` argument set to True.
# 
# Converter.__str__
# ~~~~~~~~~~~~~~~~~
# 
# Return converted data as string::

    def __str__(self):
        blocks = ["".join(block) for block in self()]
        return "".join(blocks)

# Converter.get_indent
# ~~~~~~~~~~~~~~~~~~~~
# 
# Return the number of leading spaces in `string` after expanding tabs ::

    def get_indent(self, string):
        """Return the indentation of `string`.
        """
        line = string.expandtabs()
        return len(line) - len(line.lstrip())

# Converter.ensure_trailing_blank_line
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 
# Ensure there is a blank line as last element of the list `lines`::

    def ensure_trailing_blank_line(self, lines, next_line):
        if not lines:
            return
        if lines[-1].lstrip(): 
            sys.stderr.write("\nWarning: inserted blank line between\n %s %s"
                             %(lines[-1], next_line))
            lines.append("\n")


# Text2Code
# ---------
# 
# The `Text2Code` class separates code blocks (indented literal blocks) from
# reStructured text. Code blocks are unindented, text is commented (or
# filtered, if the ``strip`` option is True.
# 
# Only `indented literal blocks` are extracted. `quoted literal blocks` and
# `pydoc blocks` are treated as text. This allows the easy inclusion of
# examples: [#]_
# 
#    >>> 23 + 3
#    26
# 
# .. [#] Mark that there is no double colon before the doctest block in
#        the text source.
# 
# The state handlers are implemented as generators. Iterating over a
# `Text2Code` instance initializes them to generate iterators for
# the respective states (see ``simplestates.py``).
# 
# ::

class Text2Code(PyLitConverter):
    """Convert a (reStructured) text source to code source
    """

# Text2Code.header
# ~~~~~~~~~~~~~~~~
# 
# Convert the header (leading rst comment block) to code::

    def header(self):
        """Convert header (comment) to code"""
        line = self.data_iterator.next()

# Test first line for rst comment: (We need to do this explicitely here, as
# the code handler will only recognize the start of a text block if a line
# starting with "matching comment" is preceded by an empty line. However, we
# have to care for the case of the first line beeing a "text line".
# 
# Which variant is better?
# 
# 1. starts with comment marker and has
#    something behind the comment on the first line::

        # if line.startswith("..") and len(line.rstrip()) > 2:

# 2. Convert any leading comment to code::

        if line.startswith(self.header_string):
            
# Strip leading comment string (typically added by `Code2Text.header`) and
# return the result of processing the data with the code handler::

            self.data_iterator.push(line.replace(self.header_string, "", 1))
            return self.code()
        
# No header code found: Push back first non-header line and set state to
# "text"::

        self.data_iterator.push(line)
        self.state = 'text'
        return []

# Text2Code.text_handler_generator
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 
# The 'text' handler processes everything that is not an indented literal
# comment. Text is quoted with `self.comment_string` or filtered (with
# strip=True). 
# 
# It is implemented as a generator function that acts on the `data` iterator
# and yields text blocks.
# 
# Declaration and initialization::

    def text_handler_generator(self):
        """Convert text blocks from rst to comment
        """
        lines = []
        
# Iterate over the data_iterator (which yields the data lines)::
          
        for line in self.data_iterator:
            # print "Text: '%s'"%line
            
# Default action: add comment string and collect in `lines` list::

            lines.append(self.comment_string + line)
                
# Test for the end of the text block: a line that ends with `::` but is neither
# a comment nor a directive::

            if (line.rstrip().endswith("::")
                and not line.lstrip().startswith("..")):
                
# End of text block is detected, now:
# 
# set the current text indent level (needed by the code handler to find the
# end of code block) and set the state to "code" (i.e. the next call of
# `self.next` goes to the code handler)::

                self._textindent = self.get_indent(line)
                self.state = 'code'
                
# Ensure a trailing blank line (which is the paragraph separator in
# reStructured Text. Look at the next line, if it is blank -- OK, if it is
# not blank, push it back (it should be code) and add a line by calling the
# `ensure_trailing_blank_line` method (which also issues a warning)::

                line = self.data_iterator.next()
                if line.lstrip():
                    self.data_iterator.push(line) # push back
                    self.ensure_trailing_blank_line(lines, line)
                else:
                    lines.append(line)

# Now yield and reset the lines. (There was a function call to remove a
# literal marker (if on a line on itself) to shorten the comment. However,
# this behaviour was removed as the resulting difference in line numbers leads
# to misleading error messages in doctests)::

                #remove_literal_marker(lines)
                yield lines
                lines = []
                
# End of data: if we "fall of" the iteration loop, just join and return the
# lines::

        yield lines


# Text2Code.code_handler_generator
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 
# The `code` handler is called when a literal block marker is encounterd. It
# returns a code block (indented literal block), removing leading whitespace
# up to the indentation of the first code line in the file (this deviation
# from docutils behaviour allows indented blocks of Python code).
# 
# As the code handler detects the switch to "text" state by looking at
# the line indents, it needs to push back the last probed data token. I.e.
# the  data_iterator must support a `push` method. (This is the
# reason for the use of the PushIterator class in `__init__`.) ::

    def code_handler_generator(self):
        """Convert indented literal blocks to source code
        """
        lines = []
        codeindent = None  # indent of first non-blank code line, set below
        indent_string = "" # leading whitespace chars ...
        
# Iterate over the lines in the input data::

        for line in self.data_iterator:
            # print "Code: '%s'"%line
            
# Pass on blank lines (no test for end of code block needed|possible)::

            if not line.rstrip():
                lines.append(line.replace(indent_string, "", 1))
                continue

# Test for end of code block:
# 
# A literal block ends with the first less indented, nonblank line.
# `self._textindent` is set by the text handler to the indent of the
# preceding paragraph. 
# 
# To prevent problems with different tabulator settings, hard tabs in code
# lines  are expanded with the `expandtabs` string method when calculating the
# indentation (i.e. replaced by 8 spaces, by default).
# 
# ::

            if self.get_indent(line) <= self._textindent:
                # push back line
                self.data_iterator.push(line) 
                self.state = 'text'
                # append blank line (if not already present)
                self.ensure_trailing_blank_line(lines, line)
                yield lines
                # reset list of lines
                lines = []
                continue

# OK, we are sure now that the current line is neither blank nor a text line.
# 
# If still unset, determine the code indentation from first non-blank code
# line::

            if codeindent is None and line.lstrip():
                codeindent = self.get_indent(line)
                indent_string = line[:codeindent]
            
# Append unindented line to lines cache (but check if we can safely unindent
# first)::

            if not line.startswith(indent_string):
                raise ValueError, "cannot unindent line %r,\n"%line \
                + "  doesnot start with code indent string %r"%indent_string
            
            lines.append(line[codeindent:])

# No more lines in the input data: just return what we have::
            
        yield lines
                        

# Txt2Code.remove_literal_marker
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 
# Remove literal marker (::) in "expanded form" i.e. in a paragraph on its own.
# 
# While cleaning up the code source, it leads to confusion for doctest and
# searches (e.g. grep) as line-numbers between text and code source will
# differ. ::

    def remove_literal_marker(list):
        try:
            # print lines[-3:]
            if (lines[-3].strip() == self.comment_string.strip() 
                and lines[-2].strip() == self.comment_string + '::'):
                del(lines[-3:-1])
        except IndexError:
            pass

# Text2Code.iter_strip
# ~~~~~~~~~~~~~~~~~~~~
# 
# Modification of the `simplestates.__iter__` method that will replace it when
# the `strip` keyword argument is `True` during class instantiation: 
# 
# Iterate over class instances dropping text blocks::

    def iter_strip(self):
        """Generate and return an iterator dropping text blocks
        """
        self.data_iterator = self.data
        self._initialize_state_generators()
        while True:
            yield getattr(self, self.state)()
            getattr(self, self.state)() # drop text block



# Code2Text
# ---------
# 
# The `Code2Text` class does the opposite of `Text2Code`_ -- it processes
# valid source code, extracts comments, and puts non-commented code in literal
# blocks. 
# 
# Only lines starting with a comment string matching the one in the
# `comment_string` data attribute are considered text lines.
# 
# The class is derived from the PyLitConverter state machine and adds handlers
# for the three states "header", "text", and "code". ::

class Code2Text(PyLitConverter):
    """Convert code source to text source
    """

# Code2Text.header
# ~~~~~~~~~~~~~~~~
# 
# Sometimes code needs to remain on the first line(s) of the document to be
# valid. The most common example is the "shebang" line that tells a POSIX
# shell how to process an executable file::

#!/usr/bin/env python

# In Python, the ``# -*- coding: iso-8859-1 -*-`` line must occure before any
# other comment or code.
# 
# If we want to keep the line numbers in sync for text and code source, the
# reStructured Text markup for these header lines must start at the same line
# as the first header line. Therfore, header lines could not be marked as
# literal block (this would require the "::" and an empty line above the code).
# 
# OTOH, a comment may start at the same line as the comment marker and it
# includes subsequent indented lines. Comments are visible in the reStructured
# Text source but hidden in the pretty-printed output.
# 
# With a header converted to comment in the text source, everything before the
# first text block (i.e. before the first paragraph using the matching comment
# string) will be hidden away (in HTML or PDF output). 
# 
# This seems a good compromise, the advantages
# 
# * line numbers are kept
# * the "normal" code conversion rules (indent/unindent by `codeindent` apply
# * greater flexibility: you can hide a repeating header in a project
#   consisting of many source files.
# 
# set off the disadvantages
# 
# - it may come as surprise if a part of the file is not "printed",
# - one more syntax element to learn for rst newbees to start with pylit,
#   (however, starting from the code source, this will be auto-generated)
# 
# In the case that there is no matching comment at all, the complete code
# source will become a comment -- however, in this case it is not very likely
# the source is a literate document anyway.
# 
# If needed for the documentation, it is possible to repeat the header in (or
# after) the first text block, e.g. with a `line block` in a `block quote`:
# 
#   |  ``#!/usr/bin/env python``
#   |  ``# -*- coding: iso-8859-1 -*-``
# 
# ::

    def header(self):
        """Convert leading code to rst comment"""

# Parse with the `text` method. If there is no leading text, return the 
# `header_string` (by default the rst comment marker)::

        lines = self.text()
        if lines:
            return lines
        return [self.header_string]


# Code2Text.text_handler_generator
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 
# The text handler converts a comment to a text block if it matches the
# following requirements:
# 
# * every line starts with a matching comment string (test includes whitespace!)
# * comment is separated from code by a blank line (the paragraph separator in
#   reStructuredText)
# 
# It is implemented as a generator function that acts on the `data` iterator
# and yields text blocks.
# 
# Text is uncommented. A literal block marker is appended, if not already
# present ::

    def text_handler_generator(self):
        """Uncomment text blocks in source code
        """
        
# Set up an output cache and iterate over the data lines (remember, code lines
# are processed by the code handler and not seen here). ::
          
        lines = []
        for line in self.data_iterator:
              # print "Text: " + line
              
# Pass on blank lines. Strip comment string from otherwise blank lines
# Continue with the next line, as there is no need to test blank lines
# for the end of text. ::

            if not line.lstrip():
                lines.append(line)
                continue

# Test for end of text block: the first line that doesnot start with a
# matching comment string. This tests also whitespace that is part of the
# comment string! ::

            if not line.startswith(self.comment_string):

# Missing whitespace in the `comment_string` is not significant for otherwise
# blank lines. Add the whitespace and continue::

                if line.rstrip() == self.comment_string.rstrip():
                    lines.append(line.replace(self.comment_string.rstrip(), 
                                              self.comment_string, 1))
                    continue
    
# End of text block: Push back the line and let the "code" handler handle it
# (and subsequent lines)::
              
                self.state = 'code'
                self.data_iterator.push(line)

# Also restore and push back lines that precede the next code line without a
# blank line (paragraph separator) inbetween::
                  
                while lines and lines[-1].lstrip():
                    self.data_iterator.push(lines.pop())

# Strip the leading comment string::

                lines = [line.replace(self.comment_string, "", 1)
                         for line in lines]
                
# Ensure literal block marker (double colon) at the end of the text block::

                if len(lines)>1 and not lines[-2].rstrip().endswith("::"):
                    lines.extend(["::\n", "\n"])
                     
# Yield the text block (process following lines with `code_handler`.
# When the state is again set to "text", reset the cache and continue with 
# next text line ::
                       
                yield lines
                lines = []
                continue
                
# Test passed: It's text line. Append to the `lines` cache::

            lines.append(line)
            
# No more lines: Just return the remaining lines::
              
        yield [line.replace(self.comment_string, "", 1) for line in lines]

    
# Code2Text.code_handler_generator
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 
# The `code` method is called on non-commented code. Code is returned as
# indented literal block (or filtered, if ``strip=True``). The amount of the
# code indentation is controled by `self.codeindent` (default 2). 
# 
# ::

    def code_handler_generator(self):
        """Convert source code to indented literal blocks.
        """
        lines = []
        for line in self.data_iterator:
            # yield "Code: " + line
            # pass on empty lines (only newline)
            if line == "\n":
                lines.append(line)
                continue
            # # strip comment string from blank lines
            # if line.rstrip() == self.comment_string.rstrip():
            #     lines.append("\n")
            #     continue
            
# Test for end of code block: 
# 
# * matching comment string at begin of line,
# * following a blank line. 
# 
# The test includes whitespace in `self.comment_string` normally, but ignores
# trailing whitespace if the line after the comment string is blank. ::

            if (line.startswith(self.comment_string) or
                line.rstrip() == self.comment_string.rstrip()
               ) and lines and not lines[-1].strip():
                    
                self.data_iterator.push(line)
                self.state = 'text'
                # self.ensure_trailing_blank_line(lines, line)
                yield lines
                # reset
                lines = []
                continue
            
# default action: indent by codeindent and append to lines cache::

            lines.append(" "*self.codeindent + line)
            
# no more lines in data_iterator -- return collected lines::

        yield lines
        

# Code2Text.iter_strip
# ~~~~~~~~~~~~~~~~~~~~
# 
# Modification of the `simplestates.__iter__` method that will replace it when
# the `strip` keyword argument is `True` during class instantiation: 
# 
# Iterate over class instances dropping the header block and code blocks::

    def iter_strip(self):
        """Generate and return an iterator dropping code|text blocks
        """
        self.data_iterator = self.data
        self._initialize_state_generators()
        textblock = self.header() # drop the header
        if textblock != [self.header_string]:
            self.strip_literal_marker(textblock)
            yield textblock
        while True:
            getattr(self, self.state)() # drop code blocks
            textblock = getattr(self, self.state)()
            self.strip_literal_marker(textblock)
            yield textblock


# Code2Text.strip_literal_marker
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 
# If the code block is stripped, the literal marker would lead to an error
# when the text is converted with docutils. Replace it with the equivalent of
# docutils replace rules
# 
# * strip `::`-line as well as preceding blank line if on a line on its own
# * strip `::` if it is preceded by whitespace. 
# * convert `::` to a single colon if preceded by text
# 
# `lines` should be list of text lines (with a trailing blank line). 
# It is modified in-place::

    def strip_literal_marker(self, lines):
        if len(lines) < 2:
            return
        parts = lines[-2].rsplit('::', 1)
        if lines[-2].strip() == '::':
            del(lines[-2])
            if len(lines) >= 2 and not lines[-2].lstrip():
                del(lines[-2])
        elif parts[0].rstrip() < parts[0]:
            parts[0] = parts[0].rstrip()
            lines[-2] = "".join(parts)
        else:
            lines[-2] = ":".join(parts)



# Command line use
# ================
# 
# Using this script from the command line will convert a file according to its
# extension. This default can be overridden by a couple of options.
# 
# Dual source handling
# --------------------
# 
# How to determine which source is up-to-date?
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 
# - set modification date of `oufile` to the one of `infile` 
# 
#   Points out that the source files are 'synchronized'. 
#   
#   * Are there problems to expect from "backdating" a file? Which?
# 
#     Looking at http://www.unix.com/showthread.php?t=20526, it seems
#     perfectly legal to set `mtime` (while leaving `ctime`) as `mtime` is a
#     description of the "actuality" of the data in the file.
# 
#   * Should this become a default or an option?
# 
# - alternatively move input file to a backup copy (with option: `--replace`)
#   
# - check modification date before overwriting 
#   (with option: `--overwrite=update`)
#   
# - check modification date before editing (implemented as `Jed editor`_
#   function `pylit_check()` in `pylit.sl`_)
# 
# .. _Jed editor: http://www.jedsoft.org/jed/
# .. _pylit.sl: http://jedmodes.sourceforge.net/mode/pylit/
# 
# Recognised Filename Extensions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 
# Finding an easy to remember, unused filename extension is not easy.
# 
# .py.txt
#   a double extension (similar to .tar.gz, say) seems most appropriate
#   (at least on UNIX). However, it fails on FAT16 filesystems.
#   The same scheme can be used for c.txt, p.txt and the like.
# 
# .pytxt
#   is recognised as extension by os.path.splitext but also fails on FAT16
# 
# .pyt 
#   (PYthon Text) is used by the Python test interpreter
#   `pytest <http:www.zetadev.com/software/pytest/>`__
# 
# .pyl
#   was even mentioned as extension for "literate Python" files in an
#   email exchange (http://www.python.org/tim_one/000115.html) but 
#   subsequently used for Python libraries.
# 
# .lpy 
#   seems to be free (as by a Google search, "lpy" is the name of a python
#   code pretty printer but this should not pose a problem).
# 
# .tpy
#   seems to be free as well.
# 
# Instead of defining a new extension for "pylit" literate programms,
# by default ``.txt`` will be appended for literate code and stripped by
# the conversion to executable code. i.e. for a program foo:
# 
# * the literate source is called ``foo.py.txt``
# * the html rendering is called ``foo.py.html``
# * the python source is called ``foo.py``
# 
# 
# 
# OptionValues
# ------------
# 
# For use as keyword arguments, it is handy to have the options
# in a dictionary. The following class adds an `as_dict` method
# to  `optparse.Values`::

class OptionValues(optparse.Values):
    def as_dict(self):
        """Return options as dictionary object"""
        return dict([(option, getattr(self, option)) for option in dir(self)
                     if option not in dir(OptionValues)
                     and option is not None
                    ])
 
# PylitOptions
# ------------
# 
# Options are stored in the values attribute of the `PylitOptions` class.
# It is initialized with default values and parsed command line options (and
# arguments)  This scheme allows easy customization by code importing the
# `pylit` module. ::

class PylitOptions(object):
    """Storage and handling of program options
    """

# Recognized file extensions for text and code versions of the source:: 

    code_languages  = {".py": "python", 
                       ".sl": "slang", 
                       ".c": "c++"}
    code_extensions = code_languages.keys()
    text_extensions = [".txt"]

# Instantiation       
# ~~~~~~~~~~~~~
# 
# Instantiation sets up an OptionParser and initializes it with pylit's
# command line options and `default_values`. It then updates the values based
# on command line options and sensible defaults::

    def __init__(self, args=sys.argv[1:], **default_values):
        """Set up an `OptionParser` instance and parse and complete arguments
        """
        p = optparse.OptionParser(usage=main.__doc__, version="0.2")
        # set defaults
        p.set_defaults(**default_values)
        # add the options
        p.add_option("-c", "--code2txt", dest="txt2code", action="store_false",
                     help="convert code to reStructured text")
        p.add_option("--comment-string", dest="comment_string",
                     help="text block marker (default '# ' (for Python))" )
        p.add_option("-d", "--diff", action="store_true", 
                     help="test for differences to existing file")
        p.add_option("--doctest", action="store_true",
                     help="run doctest.testfile() on the text version")
        p.add_option("-e", "--execute", action="store_true",
                     help="execute code (Python only)")
        p.add_option("-f", "--infile",
                     help="input file name ('-' for stdout)" )
        p.add_option("--overwrite", action="store", 
                     choices = ["yes", "update", "no"],
                     help="overwrite output file (default 'update')")
        p.add_option("-o", "--outfile",
                     help="output file name ('-' for stdout)" )
        p.add_option("--replace", action="store_true",
                     help="move infile to a backup copy (appending '~')")
        p.add_option("-s", "--strip", action="store_true",
                     help="export by stripping text or code")
        p.add_option("-t", "--txt2code", action="store_true",
                     help="convert reStructured text to code")
        self.parser = p
        
        # parse to fill a self.Values instance
        self.values = self.parse_args(args)
        # complete with context-sensitive defaults
        self.values = self.complete_values(self.values)

# Calling
# ~~~~~~~
# 
# "Calling" an instance updates the option values based on command line
# arguments and default values and does a completion of the options based on
# "context-sensitive defaults"::

    def __call__(self, args=sys.argv[1:], **default_values):
        """parse and complete command line args
        """
        values = self.parse_args(args, **default_values)
        return self.complete_values(values)


# PylitOptions.parse_args
# ~~~~~~~~~~~~~~~~~~~~~~~
# 
# The `parse_args` method calls the `optparse.OptionParser` on command
# line or provided args and returns the result as `PylitOptions.Values`
# instance.  Defaults can be provided as keyword arguments::

    def parse_args(self, args=sys.argv[1:], **default_values):
        """parse command line arguments using `optparse.OptionParser`
        
           args           --  list of command line arguments.
           default_values --  dictionary of option defaults
        """
        # update defaults
        defaults = self.parser.defaults.copy()
        defaults.update(default_values)
        # parse arguments
        (values, args) = self.parser.parse_args(args, OptionValues(defaults))
        # Convert FILE and OUTFILE positional args to option values
        # (other positional arguments are ignored)
        try:
            values.infile = args[0]
            values.outfile = args[1]
        except IndexError:
            pass
        return values

# PylitOptions.complete_values
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 
# The `complete` method uses context information to set missing option values
# to sensible defaults (if possible).
# 
# ::

    def complete_values(self, values):
        """complete option values with context sensible defaults
        """
        values.ensure_value("infile", "")
        # Guess conversion direction from infile filename
        if values.ensure_value("txt2code", None) is None:
            in_extension = os.path.splitext(values.infile)[1]
            if in_extension in self.text_extensions:
                values.txt2code = True
            elif in_extension in self.code_extensions:
                values.txt2code = False
        # Auto-determine the output file name
        values.ensure_value("outfile", self.get_outfile_name(values.infile, 
                                                             values.txt2code))
        # Guess conversion direction from outfile filename or set to default
        if values.txt2code is None:
            out_extension = os.path.splitext(values.outfile)[1]
            values.txt2code = not (out_extension in self.text_extensions)
        
        # Set the language of the code (default "python")
        if values.txt2code is True:
            code_extension = os.path.splitext(values.outfile)[1]
        elif values.txt2code is False:
            code_extension = os.path.splitext(values.infile)[1]
        values.ensure_value("language", 
                            self.code_languages.get(code_extension, "python"))
        
        # Set the default overwrite mode
        values.ensure_value("overwrite", 'update')

        return values

# PylitOptions.get_outfile_name
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 
# Construct a matching filename for the output file. The output filename is
# constructed from `infile` by the following rules:
# 
# * '-' (stdin) results in '-' (stdout)
# * strip the `txt_extension` or add the `code_extension` (txt2code)
# * add a `txt_ extension` (code2txt)
# * fallback: if no guess can be made, add ".out"
# 
# ::

    def get_outfile_name(self, infile, txt2code=None):
        """Return a matching output filename for `infile`
        """
        # if input is stdin, default output is stdout
        if infile == '-':
            return '-'
        # Modify `infile`
        (base, ext) = os.path.splitext(infile)
        # TODO: should get_outfile_name() use self.values.outfile_extension
        #       if it exists?
        
        # strip text extension
        if ext in self.text_extensions: 
            return base
        # add (first) text extension for code files
        if ext in self.code_extensions or txt2code == False:
            return infile + self.text_extensions[0]
        # give up
        return infile + ".out"



# Helper functions
# ----------------
# 
# open_streams
# ~~~~~~~~~~~~
# 
# Return file objects for in- and output. If the input path is missing,
# write usage and abort. (An alternative would be to use stdin as default.
# However,  this leaves the uninitiated user with a non-responding application
# if (s)he just tries the script without any arguments) ::

def open_streams(infile = '-', outfile = '-', overwrite='update', **keyw):
    """Open and return the input and output stream
    
    open_streams(infile, outfile) -> (in_stream, out_stream)
    
    in_stream   --  file(infile) or sys.stdin
    out_stream  --  file(outfile) or sys.stdout
    overwrite   --  ['yes', 'update', 'no']
                    if 'update', only open output file if it is older than
                    the input stream.
                    Irrelevant if outfile == '-'.
    """
    if not infile:
        strerror = "Missing input file name ('-' for stdin; -h for help)"
        raise IOError, (2, strerror, infile)
    if infile == '-':
        in_stream = sys.stdin
    else:
        in_stream = file(infile, 'r')
    if outfile == '-':
        out_stream = sys.stdout
    elif overwrite == 'no' and os.path.exists(outfile):
        raise IOError, (1, "Output file exists!", outfile)
    elif overwrite == 'update' and is_newer(outfile, infile):
        raise IOError, (1, "Output file is newer than input file!", outfile)
    else:
        out_stream = file(outfile, 'w')
    return (in_stream, out_stream)

# is_newer
# ~~~~~~~~
# 
# ::  

def is_newer(path1, path2):
    """Check if `path1` is newer than `path2` (using mtime)
    
    Compare modification time of files at path1 and path2.
    
    Non-existing files are considered oldest: Return False if path1 doesnot
    exist and True if path2 doesnot exist.
    
    Return None for equal modification time. (This evaluates to False in a
    boolean context but allows a test for equality.)
    
    """
    try:
        mtime1 = os.path.getmtime(path1)
    except OSError:
        mtime1 = -1
    try:
        mtime2 = os.path.getmtime(path2)
    except OSError:
        mtime2 = -1
    # print "mtime1", mtime1, path1, "\n", "mtime2", mtime2, path2
    
    if mtime1 == mtime2:
        return None
    return mtime1 > mtime2


# get_converter
# ~~~~~~~~~~~~~
# 
# Get an instance of the converter state machine::

def get_converter(data, txt2code=True, **keyw):
    if txt2code:
        return Text2Code(data, **keyw)
    else:
        return Code2Text(data, **keyw)


# Use cases
# ---------
# 
# run_doctest
# ~~~~~~~~~~~
# 
# ::

def run_doctest(infile="-", txt2code=True, 
                globs={}, verbose=False, optionflags=0, **keyw):
    """run doctest on the text source
    """
    from doctest import DocTestParser, DocTestRunner
    (data, out_stream) = open_streams(infile, "-")
    
# If source is code, convert to text, as tests in comments are not found by
# doctest::
    
    if txt2code is False: 
        converter = Code2Text(data, **keyw)
        docstring = str(converter)
    else: 
        docstring = data.read()
        
# Use the doctest Advanced API to do all doctests in a given string::
    
    test = DocTestParser().get_doctest(docstring, globs={}, name="", 
                                           filename=infile, lineno=0)
    runner = DocTestRunner(verbose=verbose, optionflags=optionflags)
    runner.run(test)
    runner.summarize
    if not runner.failures:
        print "%d failures in %d tests"%(runner.failures, runner.tries)
    return runner.failures, runner.tries


# diff
# ~~~~
# 
# ::

def diff(infile='-', outfile='-', txt2code=True, **keyw):
    """Report differences between converted infile and existing outfile
    
    If outfile is '-', do a round-trip conversion and report differences
    """
    
    import difflib
    
    instream = file(infile)
    # for diffing, we need a copy of the data as list::
    data = instream.readlines()
    # convert
    converter = get_converter(data, txt2code, **keyw)
    new = str(converter).splitlines(True)
    
    if outfile != '-':
        outstream = file(outfile)
        old = outstream.readlines()
        oldname = outfile
        newname = "<conversion of %s>"%infile
    else:
        old = data
        oldname = infile
        # back-convert the output data
        converter = get_converter(new, not txt2code)
        new = str(converter).splitlines(True)
        newname = "<round-conversion of %s>"%infile
        
    # find and print the differences
    delta = list(difflib.unified_diff(old, new, fromfile=oldname, 
                                      tofile=newname))
    if not delta:
        print oldname
        print newname
        print "no differences found"
        return False
    print "".join(delta)
    return True
       
# main
# ----
# 
# If this script is called from the command line, the `main` function will
# convert the input (file or stdin) between text and code formats.

# Customization
# ~~~~~~~~~~~~~
# 
# Option defaults for the conversion can be as keyword arguments to `main`_. 
# The option defaults will be updated by command line options and extended
# with "intelligent guesses" by `PylitOptions` and passed on to helper
# functions and the converter instantiation.

# This allows easy customization for programmatic use -- just or call `main`
# with the appropriate keyword options (or with a `option_defaults`
# dictionary.), e.g.:

# >>> option_defaults = {'language': "c++",
# ...                    'codeindent': 4,
# ...                    'header_string': '..admonition::'
# ...                   }
#
# >>> main(**option_defaults)
#
# ::

def main(args=sys.argv[1:], **option_defaults):
    """%prog [options] FILE [OUTFILE]
    
    Convert between reStructured Text with embedded code, and
    Source code with embedded text comment blocks"""

# Parse and complete the options::

    options = PylitOptions(args, **option_defaults).values

# Run doctests if ``--doctest`` option is set::

    if options.ensure_value("doctest", None):
        return run_doctest(**options.as_dict())

# Do a round-trip and report differences if the ``--diff`` opton is set::

    if options.ensure_value("diff", None):
        return diff(**options.as_dict())

# Open in- and output streams::

    try:
        (data, out_stream) = open_streams(**options.as_dict())
    except IOError, ex:
        print "IOError: %s %s" % (ex.filename, ex.strerror)
        sys.exit(ex.errno)
    
# Get a converter instance::

    converter = get_converter(data, **options.as_dict())
    
# Execute if the ``-execute`` option is set::

    if options.ensure_value("execute", None):
        print "executing " + options.infile
        if options.txt2code:
            code = str(converter)
        else:
            code = data
        exec code
        return

# Default action: Convert and write to out_stream::

    out_stream.write(str(converter))
    
    if out_stream is not sys.stdout:
        print "extract written to", out_stream.name
        out_stream.close()
        
# Rename the infile to a backup copy if ``--replace`` is set::
 
    if options.ensure_value("replace", None):
        os.rename(options.infile, options.infile + "~")
        
# If not (and input and output are from files), set the modification time
# (`mtime`) of the output file to the one of the input file to indicate that
# the contained information is equal.[#]_ ::

    else:
        try:
            os.utime(options.outfile, (os.path.getatime(options.outfile),
                                       os.path.getmtime(options.infile))
                    )
        except OSError:
            pass

    ## print "mtime", os.path.getmtime(options.infile),  options.infile 
    ## print "mtime", os.path.getmtime(options.outfile), options.outfile


# .. [#] Make sure the corresponding file object (here `out_stream`) is
#        closed, as otherwise the change will be overwritten when `close` is 
#        called afterwards (either explicitely or at program exit).
# 
# Run main, if called from the command line::

if __name__ == '__main__':
    main()
 

# Open questions
# ==============
# 
# Open questions and ideas for further development
# 
# Options
# -------
# 
# * Collect option defaults in a dictionary (on module level)
# 
#   Facilitates the setting of options in programmatic use
#   
#   Use templates for the "intelligent guesses" (with Python syntax for string
#   replacement with dicts: ``"hello %(what)s" % {'what': 'world'}``)
# 
# * Is it sensible to offer the `header_string` option also as command line
#   option?
# 
# * Configurable 
#   
# Parsing Problems
# ----------------------
#     
# * How can I include a literal block that should not be in the
#   executable code (e.g. an example, an earlier version or variant)?
# 
#   Workaround: 
#     Use a `quoted literal block` (with a quotation different from
#     the comment string used for text blocks to keep it as commented over the
#     code-text round-trips.
# 
#     Python `pydoc` examples can also use the special pydoc block syntax (no
#     double colon!).
#               
#   Alternative: 
#     use a special "code block" directive or a special "no code
#     block" directive.
#     
# * ignore "matching comments" in literal strings?
# 
#   (would need a specific detection algorithm for every language that
#   supports multi-line literal strings (C++, PHP, Python)
# 
# * Warn if a comment in code will become text after round-trip?
# 
# code syntax highlight
# ---------------------
#   
# use `listing` package in LaTeX->PDF
# 
# in html, see 
# 
# * the syntax highlight support in rest2web
#   (uses the Moin-Moin Python colorizer, see a version at
#   http://www.standards-schmandards.com/2005/fangs-093/)
# * Pygments (pure Python, many languages, rst integration recipe):
#   http://pygments.org/docs/rstdirective/
# * Silvercity, enscript, ...  
# 
# Some plug-ins require a special "code block" directive instead of the
# `::`-literal block. TODO: make this an option
# 
# Ask at docutils users|developers
# 
# * How to handle docstrings in code blocks? (it would be nice to convert them
#   to rst-text if ``__docformat__ == restructuredtext``)
# 