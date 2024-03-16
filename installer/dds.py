import ctypes as c
import threading
from queue import Queue
import time
import os

subscribed = {}
msgqs = []
publishers = []

@c.CFUNCTYPE(None, c.c_char_p, c.c_char_p)
def data_available_cb(topic, json):
    global msgqs
    print(f"DDS RX: {topic} <- {json}")
    for (t,q,) in msgqs:
        if t == topic.decode():
            q.put(json.decode())

@c.CFUNCTYPE(None, c.c_char_p, c.c_int)
def sub_matched_cb(topic, change):
    print("sub matched", topic, change)

@c.CFUNCTYPE(None, c.c_char_p, c.c_int)
def pub_matched_cb(topic, change):
    print("pub matched", topic, change)

dds_intf = c.CDLL(os.path.join(os.path.dirname(__file__), "libdds_intf.so"))
dds_intf.initDDS(3)

dds_intf.createJSONSubscriber.restype = c.c_void_p
dds_intf.createJSONPublisher.restype = c.c_void_p

def subscribe(topic):
    if topic not in subscribed:
        p = dds_intf.createJSONSubscriber(c.c_char_p(topic.encode()), data_available_cb, sub_matched_cb)
        if p is not None:
            subscribed[topic] = p
    q = Queue()
    msgqs.append((topic, q,))
    return q

def publisher(topic):
    p = dds_intf.createJSONPublisher(c.c_char_p(topic.encode()), pub_matched_cb)
    publishers.append(p)
    return lambda json: dds_intf.publishJSON(p, c.c_char_p(json.encode()))

shutdownq = Queue() # if all you have is a hammer...
def sleep_in_background():
    shutdownq.get()
t1 = threading.Thread(target = sleep_in_background)
t1.start()

def shutdown():
#    print("cleaning up subscribers...")
#    for topic in subscribed:
#        subscriber = subscribed[topic]
#        print(subscriber)
#        dds_intf.deleteJSONSubscriber(c.c_void_p(subscriber))
#    print("cleaning up publishers...")
#    for pub in publishers:
#        print(pub)
#        dds_intf.deleteJSONPublisher(pub)
#    print("shutting down DDS")
#    dds_intf.stopDDS()
    print("shutting down Python DDS thread")
    shutdownq.put(True)


