#! /usr/bin/env python

import requests
import os
import re
import sys
import json
import urlparse
import subprocess
import datetime

import shutil


def file_get_contents(filename):
  with open(filename) as f:
    return f.read()

out_rel_path = str(datetime.datetime.now().year)
out_rel_url = out_rel_path + '/'

# Abs URL to Year's Tropical Cyclone Advisory Archive
index_url = urlparse.urljoin('http://www.nhc.noaa.gov/archive/', out_rel_url)
# abs path to web site location
root_path = os.path.abspath('.')
# abs path to output images & videos
out_path = os.path.join(root_path, out_rel_path)

name_to_id_map = {}
id_to_name_map = {}

r = requests.get(index_url)
if r.status_code >= 300:
  print 'done'

archive_html = r.content

if os.path.exists('debug-flag.txt'):
  archive_html = '''<td valign="top" headers="al">
    <!-- atcf_index=al02 --><a href="BRET.shtml?">Tropical Storm BRET</a><br>
    blaaaa
  '''

for line in archive_html.splitlines():
  match = re.match(r'.*?atcf_index=(al..).* (\w+)</a>.*', line)
  if match:
    id = match.group(1).upper()+'2017'
    name = match.group(2).title()
    id_to_name_map[id] = name
    name_to_id_map[name] = id

arc_prefix = 'http://www.nhc.noaa.gov/archive/2017/graphics/'

for name, id in name_to_id_map.items():
  print name, id

  path = os.path.join(out_path, name)

  arc_folder = urlparse.urljoin(arc_prefix, id + '/')

  ir = requests.get(arc_folder)
  if ir.status_code>=300:
    print "No archive folder for %s" % name
    break

  print ""
  print arc_folder
  print ""

  images = []
  for line in ir.content.splitlines():
    #AL112017_5day_cone_with_line_1.png
    match = re.search(r'AL\d{6}_5day_cone_with_line_\d\w*\.png', line)
    if match:
      images.append(match.group(0))
      #print match.group(0)

  print ""

  if len(images) == 0:
    continue

  if not os.path.exists(path):
    os.makedirs(path)

  if not os.path.exists(path):
    print "Can't create directory %s" % path
    sys.exit(1)

  files_txt = json.dumps(images)
  files_txt_path = os.path.join(path, 'files.json')

  files_done = []
  new_images = False

  if os.path.exists(files_txt_path):
    json_str = file_get_contents(files_txt_path)
    try:
      file_list = json.loads(json_str)
    except ValueError:
      pass
    else:
      files_done = file_list

  last_image_path = None

  for num, image in enumerate(images, start=1):

    file_url = urlparse.urljoin(arc_folder, image)
    file_name = 'image_%03d.png' % num
    file_path = os.path.join(path, file_name)

    last_image_path = file_path

    if image in files_done:
      pass
    else:
      print 'Downloading', file_url
      imgr = requests.get(file_url)
      if imgr.status_code < 300:
        with open(file_path, 'wb') as output:
          output.write(imgr.content)
          files_done.append(image)
          new_images = True

      if image == images[-1]:
        poster_path = os.path.join(path, '%s.png' % name)
        with open(poster_path, 'wb') as output:
          output.write(imgr.content)

  if len(files_done):
    with open(files_txt_path, 'w') as output:
      output.write(json.dumps(files_done))

  video_name = '%s.mp4' % name
  video_path = os.path.join(path, video_name)

  if new_images or not os.path.exists(video_path):
    input_glob = os.path.join(path, 'image*.png')
    print 'Creating video:', video_name
    subprocess.call(['convert', '-delay', '15', '-loop', '0', input_glob, '-resize', '200%',  video_path])

    subprocess.call(['chmod', 'ga+r', video_path])

  poster_name = '%s.png' % name
  poster_path = os.path.join(path, poster_name)

  print poster_path, 'yes' if os.path.exists(poster_path) else 'no'
  if not os.path.exists(poster_path):
    shutil.copyfile(last_image_path, poster_path)
    print 'copying last image to poster', last_image_path, 'to', poster_path

index_path = os.path.join(root_path, 'index.html')
raw_tmpl = file_get_contents(os.path.join(root_path, 'template.html'))


def replacer(match):
  frag_name = match.group(1)
  frag_path = os.path.join(root_path, frag_name)
  if os.path.exists(frag_path):
    return file_get_contents(frag_path)
  else:
    return '<!-- no replacement for %s -->' % frag_name

tmpl = re.sub(r'<!--\s*INSERT:\s*(\S*?)\s*-->', replacer, raw_tmpl).replace('{YEAR}', out_rel_path)

tmpl_parts = tmpl.split('<!--SPLIT-->')
with open(index_path, 'w') as output:
  output.write(tmpl_parts[0])
  for id in sorted(id_to_name_map.keys(), reverse=True):
    name = id_to_name_map[id]
    video_rel_path = os.path.join(name, '%s.mp4' % name)
    video_path = os.path.join(out_path, video_rel_path)
    poster_rel_path = os.path.join(name, '%s.png' % name)
    poster_path = os.path.join(out_path, poster_rel_path)
    if os.path.exists(video_path) and os.path.exists(poster_path):
      video_tmpl = tmpl_parts[1]
      output.write(video_tmpl.replace('{STORM_NAME}', name))
  output.write(tmpl_parts[-1])