Library to parse and apply unified diffs.

### Features

 * Python 2 and 3 compatible
 * Automatic correction of
   * Linefeeds according to patched file
   * Diffs broken by stripping trailing whitespace
   * a/ and b/ prefixes
 * Single file, which is a command line tool and a library
 * No dependencies outside Python stdlib
 * Patch format detection (SVN, HG, GIT)
 * Nice diffstat histogram
 * Linux / Windows / OS X
 * Test coverage

Things that don't work out of the box:

 * File renaming, creation and removal
 * Directory tree operations
 * Version control specific properties
 * Non-unified diff formats

## Credits

Anatoly Techtonik
Alex Stewart
Wladimir J. van der Laan (laanwj)
azasypkin
Philippe Ombredanne
mspncp
Yen Chi Hsuan (@yan12125)
Maciej Kucia
