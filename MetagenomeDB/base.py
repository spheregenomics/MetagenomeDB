# base.py: root class abstracting the MongoDB content

import connection, forge, tree, errors, commons
import pymongo
import sys

class Object (object):

	# Create a new object wrapping a MongoDB collection.
	# - properties: dictionary of key/values for this object
	# - indices: dictionary of which keys will be set as indexes for the
	#   MongoDB collection. Values are booleans that indicate if this index
	#   must contains unique values.
	def __init__ (self, properties, indices):
		self.__properties = {}
		self.__indices = indices

		for key, value in properties.iteritems():
			key = tree.validate_key(key)
			tree.set(self.__properties, key, value)

		# if the object is provided with an identifier,
		# we check if this identifier is present in the
		# object cache to know if it was committed.
		if ("_id" in self.__properties):
			id = self.__properties["_id"]

			if (type(id) == str):
				id = pymongo.objectid.ObjectId(id)
				self.__properties["_id"] = id

			if (not forge.exists(id)):
				raise ValueError("Unknown identifier '%s'" % id)

			self.__committed = True
		else:
			self.__committed = False

	#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::: Class methods

	# Count the number of instances of this object in the database
	@classmethod
	def count (cls, **filter):
		return forge.count(cls.__name__, query = filter)

	# Retrieve distinct values (and number of objects having this value) for
	# a given property
	@classmethod
	def distinct (cls, property):
		return forge.distinct(cls.__name__, property)

	# Select instances of this object that pass a filter,
	# expressed as a set of (possibly) nested key/values.
	# If no filter is provided, all instances are returned.
	@classmethod
	def find (cls, **filter):
		return forge.find(cls.__name__, query = filter)

	# Same as find(), but return only the first instance.
	@classmethod
	def find_one (cls, **filter):
		return forge.find(cls.__name__, query = filter, find_one = True)

	# Remove all objects of this type in the database. Note that
	# any existing instance of this object remains in memory, albeit
	# flagged as uncommitted.
	@classmethod
	def remove_all (cls):
		forge.remove_all(cls.__name__)

	#:::::::::::::::::::::::::::::::::::::::::::::::::::::::: Instances methods

	# Test if this object has been committed to the database.
	def is_committed (self):
		return self.__committed

	# Commit this instance of this object to the database.
	# The new identifier of this object is returned.
	def commit (self, **patch):
		if (self.__committed):
			return

		# If some patch needs to be applied on the object's
		# properties, we temporary store the old values
		tmp = {}
		for (key, value) in patch.iteritems():
			assert (key != "_id") ###
			tmp[key] = self.__properties[key]
			self.__properties[key] = value

		id = forge.commit(self, self.__indices)
		self.__committed = True
		self.__properties["_id"] = id

		# We restore the object's properties, if needed
		for (key, value) in tmp.iteritems():
			self.__properties[key] = value

		return id

	# Remove this object from the database. The object
	# remains in memory, albeit flagged as uncommitted.
	def remove (self):
		if (not self.__committed):
			raise errors.UncommittedObject()

		forge.remove(self)
		del self.__properties["_id"]
		self.__committed = False

	def __del__ (self):
		# if the object is destroyed due to an exception thrown during
		# its instantiation, self.__committed will not exists.
		if (not hasattr(self, "__committed")):
			return

		if ((not self.__committed) and commons.display_warnings):
			print >>sys.stderr, "WARNING: Object %s has been destroyed without having been committed" % self

	# Find neighbors of this object in the database, as declared through
	# 'Relationship' objects.
	# - direction: either INGOING (objects pointing to this object) or
	#   OUTGOING (objects pointed by this object)
	# - neighbor_class: class of the neighbors to look for
	# - neighbor_filter: neighbor filter, expressed as a nested dictionary
	# - relationship_filter: relationship filter, expressed as a nested dictionary
	# Note: This method shouldn't be called directly by the user.
	def get_neighbors (self, direction, neighbor_class, neighbor_filter, relationship_filter):
		if (not self.__committed):
			raise errors.UncommittedObject()

		return forge.neighbors(
			self,
			direction,
			neighbor_class,
			neighbor_filter,
			relationship_filter
		)

	#:::::::::::::::::::::::::::::::::::::::::::::::::: Properties manipulation

	def __setitem__ (self, key, value):
		keys = tree.validate_key(key)
		if (keys[0] == "_id"):
			raise ValueError("The property '_id' cannot be modified")

		# discard 'phantom' modifications
		if tree.contains(self.__properties, keys) and \
		   (value == tree.get(self.__properties, keys)):
			return

		tree.set(self.__properties, keys, value)
		self.__committed = False

	def __getitem__ (self, key):
		keys = tree.validate_key(key)
		return tree.get(self.__properties, keys)

	def __delitem__ (self, key):
		keys = tree.validate_key(key)
		if (keys[0] == "_id"):
			raise ValueError("The property '_id' cannot be modified")

		tree.delete(self.__properties, keys)
		self.__committed = False

	def __contains__ (self, key):
		keys = tree.validate_key(key)
		return tree.contains(self.__properties, keys)

	# Returns a copy of this object's properties, as a nested dictionary.
	def get_properties (self):
		return self.__properties.copy()

	# Return the value of a given property, or a default one if this
	# property doesn't exist.
	def get_property (self, key, default = None):
		try:
			return self.__getitem__(key)

		except KeyError:
			return default

	#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::: Misc. methods

	def __str__ (self):
		if (hasattr(self, "__committed") and self.__committed):
			return "<Object %s>" % id
		else:
			return "<Object (uncommitted)>"

	def __repr__ (self):
		return self.__str__()
