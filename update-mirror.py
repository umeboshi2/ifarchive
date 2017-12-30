#!/usr/bin/env python
import os
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

import requests


index_url = 'http://ifarchive.org/indexes/Master-Index.xml'
runtime_dir = Path(os.environ['XDG_RUNTIME_DIR'])
local_index = runtime_dir / 'ifarchive/Master-Index.xml'

#http://ifarchive.smallwhitehouse.org/if-archive/art/if-artshow/spring1999/crystal.zip


def make_url(filepath):
    return "http://ifarchive.org/{}".format(str(filepath))


def add_url(url, filename):
    cmd = ['git-annex', 'addurl', '--relaxed', '--file', filename, url]
    subprocess.check_call(cmd)
    

def get_master_index(url, filename):
    if not filename.parent.is_dir():
        filename.parent.mkdir()
    if not filename.exists():
        print("Retrieving {}".format(url))
        response = requests.get(url)
        if not response.ok:
            raise RuntimeError('unable to retrieve master index.')
        with filename.open('wb') as outfile:
            outfile.write(response.content)
            

def parse_index():
    if not local_index.exists():
        get_master_index(index_url, local_index)
    return ET.parse(str(local_index))


def parse_symlink(element):
    symlink = element.find('symlink')
    stype = symlink.attrib['type']
    if stype == 'file':
        target = Path(symlink.find('path').text)
    elif stype == 'dir':
        target = Path(symlink.find('name').text)
        
    file = Path(element.find('path').text)
    if not file.is_symlink() and file.exists():
        raise RuntimeError("Problem handling symlink {}".format(str(file)))
    if not file.is_symlink():
        file.symlink_to(target)
        cmd = ['git', 'add', str(file)]
        subprocess.check_call(cmd)
    else:
        return
    
def parse_file_element(element):
    if element.find('symlink') is not None:
        return parse_symlink(element)
    filename = element.find('path').text
    file = Path(filename)
    if file.exists() or file.is_symlink():
        print("Skipping {}".format(filename))
        return
    if not file.parent.exists():
        print("Creating {}".format(str(file.parent)))
        file.parent.mkdir()
    url = make_url(file)
    add_url(url, str(file))


def parse_directory_element(element):
    directory = Path(element.find('name').text)
    if not directory.is_dir():
        print("Creating {}".format(str(directory)))
        directory.mkdir()
        
parsers = dict(file=parse_file_element, directory=parse_directory_element)

    
p = parse_index()
r = p.getroot()
children = r.getchildren()
for child in r.getchildren():
    tags = ['file', 'directory']
    if child.tag not in tags:
        raise RuntimeError('Unrecognized tag {}.'.format(child.tag))
        
    #parse_file_element(child)
    parsers[child.tag](child)
    
