#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import re

from target import *

out = logging.getLogger('mtui')

class Template:
	"""input handling of QA Maintenance template file"""
	def __init__(self, md5, team=None, directory=None):
		"""open and parse maintenance template file

		Keyword arguments:
		md5       -- md5 checksum of patchinfo
		team      -- team suffix (emea or asia) of template file
		directory -- QA maintenance update directory

		"""
		self.md5 = md5

		if directory is not None:
			self.path = directory + '/' + md5 + '/'
		else:
			self.path = './' + md5 + '/'

		if team is None:
			team = "emea"

		self.refhosts = "refhosts." + team
		self.path = self.path + 'log'
		if not os.path.isfile(self.path):
			self.path = self.path + '.' + team

		self.metadata = Metadata()
		self.metadata.md5 = md5
		self.metadata.path = self.path

		try:
			with open(self.path, 'r') as template:
				self.parse_template(template)
		except IOError as error:
			out.error("unable to open template: %s" % error.strerror)
			raise

	def parse_template(self, template):
		"""parse maintenance template file

		parses metadata from QA maintenance template file

		Keyword arguments:
		template -- template file contents

		"""
		for line in template.readlines():
			match = re.search("Category: (.+)", line)
			if match:
				self.metadata.category = match.group(1)

			match = re.search("YOU Patch No: (\d+)", line)
			if match:
				self.metadata.patches["you"] = match.group(1)

			match = re.search("ZYPP Patch No: (\d+)", line)
			if match:
				self.metadata.patches["zypp"] = match.group(1)

			match = re.search("SAT Patch No: (\d+)", line)
			if match:
				self.metadata.patches["sat"] = match.group(1)

			match = re.search("SUBSWAMPID: (\d+)", line)
			if match:
				self.metadata.swampid = match.group(1)

			match = re.search("Packager: (.+)", line)
			if match:
				self.metadata.packager = match.group(1)

			match = re.search("Packages: (.+)", line)
			if match:
				self.metadata.packages = dict([(pack.split()[0],pack.split()[2]) for pack in match.group(1).split(",")])

			match = re.search("(.*-.*) \(reference host: (.+)\)", line)
			if match:
				if '?' in match.group(2):
					hostname = self.get_refhost(match.group(1))
					out.warning("no hostname defined for system %s, using %s" % (match.group(1), hostname))
				else:
					hostname = match.group(2)

				self.metadata.systems[hostname] = match.group(1)

			match = re.search("Bug #(\d+) \(\"(.*)\"\):", line) # deprecated
			if match:
				self.metadata.bugs[match.group(1)] = match.group(2)

			match = re.search("Bugs: (.*)", line)
			if match:
				for bug in match.group(1).split(','):
					self.metadata.bugs[bug.strip(' ')] = "Description not available"

	def get_refhost(self, system):
		"""get refhost from system name

		parses refhost mapping file to get testing machine

		Keyword arguments:
		system -- requested system name

		"""
		refhostfile = os.path.dirname(__file__) + "/" + self.refhosts

		try:
			with open(refhostfile, 'r') as reffile:
				for line in reffile.readlines():
					match = re.search('%s="(.*)"' % system, line)
					if match:
						return match.group(1)
		except OSError as error:
			if error.errno == errno.ENOENT:
				out.warning("refhost mapping file %s not found" % self.refhosts)
			else:
				pass
		
