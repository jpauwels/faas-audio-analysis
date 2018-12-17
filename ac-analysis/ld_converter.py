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
# [
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
# ]
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

franz_ns = "http://francesco.org#"

def convert(descriptor, file_id, result_dict, output_format):
    if descriptor == 'chords':
        return convert_chords(file_id, result_dict, output_format)


def convert_chords(file_id, result_dict, output_format):
    # setting up namespaces
    afo = Namespace("https://w3id.org/afo/onto/1.1#")
    co = Namespace("http://purl.org/co/")
    ev = Namespace("http://purl.org/NET/c4dm/event.#")
    time = Namespace("http://www.w3.org/2006/time-entry#")
    ns = Namespace(franz_ns)
    g = Graph()

    # VERSION 1
    # building up the graph as suggested in
    result = URIRef("{}chords{}".format(franz_ns, str(file_id)))
    g.add((result, RDF.type, afo.AudioFeature))
    g.add((result, afo.confidence, Literal(result_dict["confidence"])))
    collectionBnode = BNode()
    g.add((result, afo.collection, collectionBnode))
    for seqID,seq in enumerate(result_dict["chordSequence"]):
        seqURI = URIRef("{}seq{}".format(franz_ns,str(seqID)))
        g.add((collectionBnode, co.hasElement, seqURI))
        g.add((seqURI, RDF.type, afo.AudioFeature))
        g.add((seqURI, RDF.type, afo.Segment))
        chordSeqInterval = BNode()
        g.add((seqURI, ev.time, chordSeqInterval))
        g.add((chordSeqInterval, RDF.type, time.Interval))
        g.add((chordSeqInterval, time.start, Literal(seq["start"])))
        g.add((chordSeqInterval, time.end, Literal(seq["end"])))
        g.add((chordSeqInterval, RDFS.label, Literal(seq["label"])))
    # END VERSION 1

    return g.serialize(format=output_format).decode("utf-8")
