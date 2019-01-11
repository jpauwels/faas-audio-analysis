#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  ld_converter.py
#
#  _     ___ ____ _____ _   _ ____  _____
# | |   |_ _/ ___| ____| \ | / ___|| ____|
# | |    | | |   |  _| |  \| \___ \|  _|
# | |___ | | |___| |___| |\  |___) | |___
# |_____|___\____|_____|_| \_|____/|_____|
#  Copyright 2018 Francesco Antoniazzi <francesco.antoniazzi1991@gmail.com>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#
#  ____  _____    _    ____  __  __ _____
# |  _ \| ____|  / \  |  _ \|  \/  | ____|
# | |_) |  _|   / _ \ | | | | |\/| |  _|
# |  _ <| |___ / ___ \| |_| | |  | | |___
# |_| \_\_____/_/   \_\____/|_|  |_|_____|
#
# in-template:
#    {
#         "confidence": double
#         "duration": double
#         "frameSpls": [doubles] --> not in the current code. Do we need them?
#         "chordSequence": [
#             {
#                 "start": double
#                 "end": double
#                 "label": "string"
#             }
#         ]
#     }
#
# triples-template:
# myResult            rdf:type               afo:AudioFeature;    (it's the outer array object)
#                     afo:confidence         xsd:float;
# ##### SOLUTION 1#######################################################
#                     afo:collection         myAFOCollection.           |
# myAFOCollection     rdf:type               purl:co:Collection;        |
#                     purl:co:hasElement     myChord1, myChord2,...     |
# #######################################################################
# ##### SOLUTION 2#######################################################
#                     afo:hasFeature         myChord1, myChord2,...     |
# #######################################################################
# myChord1            rdf:type               afo:AudioFeature, afo:Segment;
#                     purl:event:time        chordInterval.
# chordInterval       rdf:type               purl:timeline:Interval;
#                     purl:timeline:start    xsd:decimal;
#                     purl:timeline:end      xsd:decimal;
#                     rdfs:label             "cmaj".
#
#   ____ ___  ____  _____
#  / ___/ _ \|  _ \| ____|
# | |  | | | | | | |  _|
# | |__| |_| | |_| | |___
#  \____\___/|____/|_____|

from rdflib import Graph, BNode, Namespace, RDF, XSD, URIRef, RDFS, Literal
from collections import OrderedDict, Mapping
from copy import deepcopy
import logging
import json

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

afo = Namespace("https://w3id.org/afo/onto/1.1#")
collection = Namespace("http://purl.org/co/")
event = Namespace("http://purl.org/NET/c4dm/event.#")
timeline = Namespace("http://purl.org/NET/c4dm/timeline.owl#")
ns = Namespace("http://francesco.org#")
context = {
    "afo": str(afo),
    "collection": str(collection),
    "event": str(event),
    "timeline": str(timeline),
    "ns": str(ns),
    "rdfs": str(RDFS)}


def json_sort(json_object, key_listing):
    """
    Input:
    json_object: a json.loads dictionary
    key_listing: a list of lists, formatted as following

    At index 0, a list of the keys in the root object in the desired order.
    At index 1, a list of the keys in any first orded object, in the desired order.
    And so on.
    You can use the wildcard '*' to represent all the missing keys in the object:
    so, if you have as json {"hello": "ciao", "goodmorning": "buongiorno"}, you can
    1- ["goodmorning", "hello"] --> {"goodmorning": "buongiorno", "hello": "ciao"}
    2- ["*", "hello"] --> {"goodmorning": "buongiorno", "hello": "ciao"}
    3- ["goodmorning", "*"] --> {"goodmorning": "buongiorno", "hello": "ciao"}

    You can put, instead of a key-list, a list of key-lists. The most appropriate
    among them will be chosen automatically. In this case, the wildcard
    '*' is not allowed.

    Output:
    Returns the json_object ordered as requested.
    """
    if key_listing == [] or not (isinstance(json_object, Mapping) or isinstance(json_object, list)):
        # if no ordering pattern is given, or the object is literal element, just return as it is
        return json_object
    elif isinstance(json_object, Mapping):
        # if the object is a dictionary
        json_keys = set(json_object.keys())
        if isinstance(key_listing[0][0], list):
            # if we have a list of key-lists
            key_listing_copy = None
            for item in key_listing[0]:
                if "*" in item:
                    # wildcard is not allowed in this case
                    raise ValueError("'*' wildcard not allowed with alternatives")
                if json_keys == set(item):
                    # this happens when the perfect match is reached between
                    # json_object and key_listing
                    key_listing_copy = deepcopy(item)
                    break
            # raise error when perfect match is not reached
            assert key_listing_copy, "None of the given patterns applies!"
        else:
            # if we have a plain list of keys
            key_listing_copy = deepcopy(key_listing[0])
            if "*" in key_listing[0]:
                # here the wildcard is allowed
                position = key_listing[0].index("*")
                key_listing_copy.remove("*")
                key_listing_copy[position:position] = list(json_keys-set(key_listing_copy))

        # recursive part: all objects are ordered calling again this same function
        ordered = OrderedDict()
        for key in key_listing_copy:
            if key in json_keys:
                # the next call to json_sort is limited with key_listing[1::],
                # so that in the end you reach the plain return case
                ordered[key] = json_sort(json_object[key], key_listing[1::])
            else:
                # catch the key missing in case json_object does not contain the key 'key'
                logging.warning("Missing key: {}".format(key))
        return ordered
    elif isinstance(json_object, list):
        # when the object is an array, you just make recursion on every item
        return [json_sort(item, key_listing[1::]) for item in json_object]
    else:
        logging.critical("Invalid params to json_sort")
        raise ValueError("Invalid params")


def convert(descriptor, file_id, result_dict, output_format):
    if descriptor == "chords":
        serialised = convert_chords(file_id, result_dict, output_format)
    elif descriptor in ["instruments", "beats-beatroot", "keys"]:
        serialised = convert_jams(file_id, result_dict, output_format, descriptor)
    elif descriptor == "essentia-music":
        serialised = convert_essentia(file_id, result_dict, output_format)
    else:
        raise ValueError
    if output_format == 'json-ld':
        return json_sort(json.loads(serialised),
            [["@context", "@graph", "*"],
             ["*"],
             ["@id", "@type", "timeline:start", "timeline:end", "timeline:duration", "rdfs:label", "*"]
            ])
    else:
        return serialised


def convert_chords(file_id, result_dict, output_format):
    # setting up namespaces
    g = Graph()

    # building up the graph as suggested in
    result = URIRef("{}chords{}".format(str(ns), file_id))
    g.add((result, RDF.type, afo.AudioFeature))
    g.add((result, afo.confidence, Literal(result_dict["confidence"])))

    collectionBnode = BNode()
    g.add((result, afo.collection, collectionBnode))
    g.add((collectionBnode, RDF.type, collection.Collection))

    for seqID,seq in enumerate(result_dict["chordSequence"]):
        seqURI = URIRef("{}seq{}".format(str(ns),seqID))
        g.add((collectionBnode, collection.hasElement, seqURI))
        g.add((seqURI, RDF.type, afo.AudioFeature))
        g.add((seqURI, RDF.type, afo.Segment))
   
        chordSeqInterval = BNode()
        g.add((seqURI, event.time, chordSeqInterval))
        g.add((chordSeqInterval, RDF.type, timeline.Interval))
        g.add((chordSeqInterval, timeline.start, Literal(seq["start"])))
        g.add((chordSeqInterval, timeline.end, Literal(seq["end"])))
        g.add((chordSeqInterval, RDFS.label, Literal(seq["label"])))
    return g.serialize(format=output_format, context=context).decode("utf-8")


def convert_jams(file_id, result_dict, output_format, descriptor):
    g = Graph()

    result = URIRef("{}_{}_{}".format(str(ns), descriptor, file_id)) # output root
    g.add((result, RDF.type, afo.AudioFeature))
    # did not consider the "file_metadata"

    collectionBnode_annotations = BNode() # do we really need that?
    g.add((result, afo.collection, collectionBnode_annotations))
    g.add((collectionBnode_annotations, RDF.type, collection.Collection))

    # adding the content of the "annotations" key in the json
    for index, annotation in enumerate(result_dict["annotations"]):
        annotationURI = URIRef("{}annotation{}".format(str(ns), index))
        g.add((collectionBnode_annotations, collection.hasElement, annotationURI))
        g.add((annotationURI, RDF.type, afo.AudioFeature))
   
        # preparing the "data" key in the json
        collectionBnode_data = BNode() # do we really need that?
        g.add((annotationURI, afo.collection, collectionBnode_data))
        g.add((collectionBnode_data, RDF.type, collection.Collection))
   
        for sub_index, entry in enumerate(annotation["data"]):
            entryURI = URIRef("{}data{}".format(str(ns), sub_index))
            g.add((collectionBnode_data, collection.hasElement, entryURI))
            g.add((entryURI, RDF.type, afo.AudioFeature))
            g.add((entryURI, RDF.type, afo.Segment))
            g.add((entryURI, afo.confidence, Literal(entry["confidence"])))
       
            intervalBnode = BNode()
            g.add((entryURI, event.time, intervalBnode))
            g.add((intervalBnode, RDF.type, timeline.Interval))
            g.add((intervalBnode, timeline.start, Literal(entry["time"])))
            g.add((intervalBnode, timeline.duration, Literal(entry["duration"])))
        
            if "label" in entry.keys():
                g.add((entryURI, RDFS.label, Literal(entry["label"])))
            if "value" in entry.keys():
                if isinstance(entry["value"], list):
                    for data in entry["value"]:
                        g.add((entryURI, afo.value, Literal(data)))
                else:
                    g.add((entryURI, afo.value, Literal(entry["value"])))
    return g.serialize(format=output_format, context=context).decode("utf-8")

def convert_essentia(file_id, result_dict, output_format):
    raise NotImplementedError
