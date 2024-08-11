#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/fcntl.h>
#include <unistd.h>
#include <pthread.h>

#include <iostream>
#include <set>
#include "vendor/nlohmann/json.hpp"

using namespace nlohmann;

// annoyingly, we cannot just get this from dlfcn.h, because glibc version bad
# define RTLD_NEXT      ((void *) -1l)
extern "C" void *dlsym(void *handle, const char *symbol);

#define SWIZZLE(rtype, name, ...) \
    extern "C" rtype name(__VA_ARGS__) { \
        rtype (*next)(__VA_ARGS__) = (rtype(*)(__VA_ARGS__))dlsym(RTLD_NEXT, #name);

static std::set<void *> mqtt_connections;

SWIZZLE(int, MQTTAsync_createWithOptions, void **handle, const char *uri, const char *clientId, int persistence_type, void *context, void *options)
    int rv = next(handle, uri, clientId, persistence_type, context, options);
    printf("MQTTAsync_createWithOptions: URI %s -> handle %p\n", uri, *handle);
    mqtt_connections.insert(*handle);
    return rv;
}

struct MQTTAsync_message {
    char struct_id[4];
    int struct_version;
    int payloadlen;
    void *payload;
    int qos;
    int retained;
    int msgid;
    
    /* properties */
    int count;
    int max_count;
    int length;
    void *array;
};
typedef int MQTTAsync_messageArrived(void *context, char *topicName, int topicLen, struct MQTTAsync_message *message);

static MQTTAsync_messageArrived *messageArrived;

extern "C" int MQTTAsync_isConnected(void *handle);
extern "C" int MQTTAsync_sendMessage(void *handle, const char *topic, const struct MQTTAsync_message *msg, void *response);
extern "C" void MQTTAsync_freeMessage(struct MQTTAsync_message **msg);
extern "C" void MQTTAsync_free(void *p);

struct message_to_send {
    char *topic;
    char *msg;
};

static void *_send_one_message(void *ctx) {
    struct message_to_send *msgbuf = (struct message_to_send *)ctx;
    for (auto it = mqtt_connections.begin(); it != mqtt_connections.end(); it++) {
        void *handle = *it;
        if (!MQTTAsync_isConnected(handle))
            continue;
        
        MQTTAsync_message msg = {
            .struct_id = {'M', 'Q', 'T', 'M'},
            .struct_version = 0,
            .payloadlen = (int)strlen(msgbuf->msg),
            .payload = (void *)msgbuf->msg,
            .qos = 0
        };
        
        MQTTAsync_sendMessage(handle, msgbuf->topic, &msg, NULL);
    }    
    free(msgbuf->topic);
    free(msgbuf->msg);
    free(msgbuf);
    return NULL;
}

static int _messageArrived(void *context, char *topicName, int topicLen, struct MQTTAsync_message *message) {
    char *topic = strndup(topicName, topicLen);
    char *s = strndup((const char *)message->payload, message->payloadlen);
    bool passthrough = true;
    if (strstr(topic, "/request")) {
        strcpy(strstr(topic, "/request"), "/report"); /* lol. */
        try {
            json j = json::parse(s);
            auto x1plus = j.at("x1plus");
            auto synthesize = x1plus.at("synthesize_report");
            std::string synthesized = synthesize.dump();
            const char *synthesized_s = synthesized.c_str();
            std::cout << "MQTTAsync: synthesizing report " << synthesized << "\n";
            
            /* we cannot MQTTAsync_sendMessage inside the messageArrived
             * callback; we cheesily spinup a single-use thread for this,
             * since we cannot punt this to the main loop since we don't
             * have access to that from here 
             */
            struct message_to_send *msg = (struct message_to_send *)malloc(sizeof(*msg));
            msg->topic = strdup(topic);
            msg->msg = strdup(synthesized_s);
            pthread_t pth;
            pthread_attr_t attr;
            pthread_attr_init(&attr);
            pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);
            pthread_create(&pth, &attr, _send_one_message, msg);
            pthread_attr_destroy(&attr);
            
            passthrough = false;
        } catch(...) {
            /* simply pass it through */
        }
    }
    /* parse it, and if it's an x1plus rebroadcast message, then rebroadcast it to report */
    free(topic);
    free(s);
    if (passthrough) {
        return messageArrived(context, topicName, topicLen, message);
    } else {
        MQTTAsync_freeMessage(&message);
        MQTTAsync_free(topicName);
        return true;
    }
}

SWIZZLE(int, MQTTAsync_setCallbacks, void *handle, void *context, void *cl, MQTTAsync_messageArrived *ma, void *dc)
    messageArrived = ma;
    printf("MQTTAsync_setCallbacks(%p)\n", handle);
    return next(handle, context, cl, _messageArrived, dc);
}

SWIZZLE(void, MQTTAsync_destroy, void **handle)
    printf("MQTTAsync_destroy handle %p\n", *handle);
    mqtt_connections.erase(*handle);
    next(handle);
}
