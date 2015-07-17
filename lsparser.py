#!/usr/bin/env python
import os, sys
import time
import random
import subprocess
import multiprocessing
from multiprocessing.pool import ThreadPool

from ftplib import FTP

import requests

def init_git_annex():
    import socket
    hostname = socket.gethostname()
    cmd = ['git-annex', 'init', hostname]
    subprocess.check_call(cmd)
    cmd = ['git', 'config', 'remote.origin.annex-ignore', 'true']
    subprocess.check_call(cmd)
    

def get_main_list_ftp(filename):
    if not os.path.exists(filename):
        conn = FTP('ftp.ifarchive.org')
        print "Connected to ftp.ifarchive.org"
        conn.login()
        conn.cwd('if-archive')
        print "Retrieving", filename
        with file(filename, 'w') as outfile:
            conn.retrbinary('RETR %s' % filename, outfile.write)
        conn.quit()
        print "Finished", filename
    else:
        print filename, 'exists.'


def get_main_list(filename):
    if not os.path.exists(filename):
        response = requests.get('http://%s/if-archive/ls-lR' % mirror_host)
        if not response.ok:
            raise RuntimeError, response
        with file(filename, 'w') as outfile:
            outfile.write(response.content)
        
def make_single_stanza(infile, line):
    stanza = list()
    #finished = False
    while line:
        stanza.append(line)
        try:
            line = infile.next().strip()
        except StopIteration:
            return stanza
    return stanza
    
    
def make_stanzas(infile):
    stlist = list()
    line = infile.next().strip()
    while line:
        stanza = make_single_stanza(infile, line)
        stlist.append(stanza)
        try:
            line = infile.next().strip()
        except StopIteration:
            return stlist
    
def parse_parent_line(line):
    maindir = 'if-archive'
    if line[-1] != ":":
        raise RuntimeError, "Can't parse parent line: %s" % line
    if line == '%s:' % maindir:
        return '.'
    elif line.startswith('%s/' % maindir):
        line = line[len(maindir) + 1:]
    else:
        raise RuntimeError, "Can't parse parent line: %s" % line
    return line[:-1]

def parse_entry_line(line):
    if ' -> ' in line:
        if verbose:
            print "Skipping symlink %s" % line
        return dict(perms='')
    ls = line.split()
    perms = ls.pop(0)
    dsize = ls.pop(0)
    user = ls.pop(0)
    group = ls.pop(0)
    fsize = ls.pop(0)
    month = ls.pop(0)
    day = ls.pop(0)
    year = ls.pop(0)
    name = ' '.join(ls)
    # convert fields
    dsize = int(dsize)
    fsize = int(fsize)
    day = int(day)
    if ':' in year:
        year = 2015
    else:
        year = int(year)
    edata = dict(perms=perms, dsize=dsize, user=user, group=group,
                 fsize=fsize, month=month, day=day, year=year,
                 name=name)
    return edata

        
def parse_stanza(stanza):
    parent = parse_parent_line(stanza[0])
    total = int(stanza[1].split()[1])
    entry_lines = [parse_entry_line(l) for l in stanza[2:]]
    return dict(parent=parent, total=total, entries=entry_lines)

def make_stanza_directories(stanza):
    parent = stanza['parent']
    parent_path = os.path.join(topdir, parent)
    if not os.path.isdir(parent_path):
        os.mkdir(parent_path)
    for entry in stanza['entries']:
        if entry['perms'].startswith('drwx'):
            #print "Create entry", entry['name'], parent_path
            fpath = os.path.join(parent_path, entry['name'])
            if not os.path.isdir(fpath):
                #print "Creating %s" % fpath
                os.mkdir(fpath)
                
def make_file_list(stanza):
    flist = list()
    parent = stanza['parent']
    parent_path = os.path.join(topdir, parent)
    if not os.path.isdir(parent_path):
        raise RuntimeError, "Create directory %s" % parent_path
    for entry in stanza['entries']:
        if entry['perms'].startswith('-rw-'):
            fname = os.path.join(parent_path, entry['name'])
            flist.append(fname)
    return flist

def make_complete_file_list(stanzas):
    flist = list()
    for stanza in stanzas:
        flist += make_file_list(stanza)
    return flist

def make_url(relname):
    return 'http://%s/if-archive/%s' % (mirror_host, relname)

def retrieve_local_file(relname):
    filename = os.path.abspath(relname)
    url = make_url(relname)
    response = requests.get(url)
    if not response.ok:
        raise RuntimeError, response
    with file(filename, 'w') as outfile:
        outfile.write(response.content)
        
            
def check_local_file(filename):
    relname = os.path.relpath(filename)
    if relname == 'ls-lR':
        return
    if not os.path.isfile(filename):
        if os.path.islink(relname):
            return
        print "Retrieving file %s" % relname
        retrieve_local_file(relname)
        check_local_file(filename)
    else:
        if not os.path.islink(relname):
            cmd = ['git-annex', 'add', relname]
            subprocess.check_call(cmd)
            url = make_url(relname)
            cmd = ['git-annex', 'addurl', url]
            subprocess.check_call(cmd)
            
def check_local_file_url_only(filename):
    relname = os.path.relpath(filename)
    if relname == 'ls-lR':
        return
    if not os.path.isfile(filename):
        if os.path.islink(relname):
            return
        print 55*'#'
        print "Retrieving file %s" % relname
        random_seconds = random.random() 
        print "Sleeping for %s" % random_seconds
        #time.sleep(random_seconds)
        url = make_url(relname)
        cmd = ['git-annex', 'addurl', url, '--file=%s' % relname]
        subprocess.check_call(cmd)
        

lslr_filename = 'ls-lR'
verbose = False
mirror_host = 'mirror.ifarchive.org'

topdir = os.getcwd()


if __name__ == '__main__':
    if not os.path.isdir('.git/annex'):
        init_git_annex()
    foo = get_main_list(lslr_filename)
    with file(lslr_filename) as lsfile:
        sl = make_stanzas(lsfile)
    ps = [parse_stanza(s) for s in sl]
    b = ps[0]['entries'][4]
    bp = ps[0]['parent']
    [make_stanza_directories(s) for s in ps]
    fl = make_complete_file_list(ps)
    random.shuffle(fl)
    count = 0
    for f in fl:
        count += 1
        check_local_file_url_only(f)
        if not count % 20:
            subprocess.check_call(['git-annex', 'sync', 'origin'])
            
        
