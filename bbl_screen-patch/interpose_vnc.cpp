/* bbl_screen interposer to add VNC support to the linux fbdev interface
 *
 * Copyright (c) 2023 - 2024 Joshua Wise, and the X1Plus authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

// use a dirent64
#define _XOPEN_SOURCE
#define _FILE_OFFSET_BITS 64

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/fcntl.h>
#include <dirent.h>
#include <unistd.h>
#include <cmath>
#include <cstdio>
#include <sys/mman.h>
#include <dlfcn.h>

#include <xf86drm.h>
#include <QtGui/QRegion>
#include <QtGui/QWindow>
#include <QtWidgets/QApplication>
#include <QtQuick/QQuickView>
#include <rfb/rfb.h>

#define SWIZZLE(rtype, name, ...) \
    extern "C" rtype name(__VA_ARGS__) { \
        rtype (*next)(__VA_ARGS__) = (rtype(*)(__VA_ARGS__))dlsym(RTLD_NEXT, #name); \


struct fb_map {
    drm_handle_t handle;
    size_t pitch;
    size_t size;
    uint32_t w;
    uint32_t h;
    uint32_t buf_id;
    void *p;
};


#define FB_MAPS_MAX 4
static struct fb_map fb_maps[FB_MAPS_MAX] = {};

static QRegion lastRegion;
static rfbScreenInfoPtr rfbScreen = NULL;

static void fb_transpose_C(uint32_t __restrict *fbout, uint32_t __restrict *fbin) {
    struct timeval tv_start;
    gettimeofday(&tv_start, 0);
    const int W = 1280;
    const int H = 720;
    uint8_t dirtyx[W] = {};
    uint8_t dirtyy[H] = {};
    for (int y0 = 0; y0 < H; y0 += 8) {
        for (int x0 = 0; x0 < W; x0 += 8) {
            for (int y = 0; y < 8; y++) {
                for (int x = 0; x < 8; x++) {
                    uint32_t pxl = fbin[(x0 + x) * H + y0 + y];
                    pxl = ((pxl & 0xFF0000) >> 16) | (pxl & 0x00FF00) | ((pxl & 0xFF) << 16);
                    fbout[(y0+y)*W + W - (x0 + x + 1)] = pxl;
                }
            }
        }
    }

    QRect bbox = lastRegion.boundingRect();
    int sx = bbox.x(), sy = bbox.y(), dx = bbox.width(), dy = bbox.height();

    struct timeval tv_end;
    gettimeofday(&tv_end, 0);
    long usec = (tv_end.tv_sec - tv_start.tv_sec) * 1000000 + tv_end.tv_usec - tv_start.tv_usec;
    printf("(%d,%d) + (%d,%d) in %ld us\n", sx, sy, dx, dy, usec);
    rfbMarkRectAsModified(rfbScreen, sx, sy, sx+dx, sy+dy);
}

#define fb_transpose fb_transpose_neon
#include <arm_neon.h>

static int fb_should_update_all = 0;
static uint32_t *fb_most_recent;

/* about 80ms; naive C implementation above is about 150ms, so this is
 * pretty substantially better */
static void fb_transpose_neon(uint32_t __restrict *fbout, uint32_t __restrict *fbin) {
    struct timeval tv_start;
    gettimeofday(&tv_start, 0);
    const int W = 1280;
    const int H = 720;

    QRect bbox = lastRegion.boundingRect();
    int sx = bbox.x(), sy = bbox.y(), dx = bbox.width(), dy = bbox.height();
    
    if (fb_should_update_all) {
        /* a client connected and we have been delinquent on updating the framebuffer */
        sx = 0;
        sy = 0;
        dx = W;
        dy = H;
        fb_should_update_all = 0;
    }
    
    for (int y0 = sy & ~3; y0 < sy + dy; y0 += 4) {
        for (int x0 = sx & ~3; x0 < sx + dx; x0 += 4) {
            /* block (y, x) = x0, y0 goes to destination block (y, x) = y0, N-1 - x0 */
            
            /* man, GCC's codegen for this just absolutely sucks ass. */
            uint32x4_t w[4];
            
            /* ARGB flip: reverse ARGB -> BGRA, then right shift to xBGR */
            for (int i = 0; i < 4; i++) {
                uint8x16_t b;
                b = vld1q_u8((uint8_t *)(fbin + (W - (x0 + i) - 1) * H + y0));
                b = vrev32q_u8(b);
                w[i] = vreinterpretq_u32_u8(b);
                w[i] = vshrq_n_u32(w[i], 8);
            }

            /* do the transpose */
            /* input:
             * w0[0:3] = { x0y0 x0y1 x0y2 x0y3 }
             * w1[0:3] = { x1y0 x1y1 x1y2 x1y3 }
             * w2[0:3] = { x2y0 x2y1 x2y2 x2y3 }
             * w3[0:3] = { x3y0 x3y1 x3y2 x3y3 }
             *
             * output goal:
             * w0[0:3] = { x0y0 x1y0 x2y0 x3y0 }
             * w1[0:3] = { x0y1 x1y1 x2y1 x3y1 }
             * w2[0:3] = { x0y2 x1y2 x2y2 x3y2 }
             * w3[0:3] = { x0y3 x1y3 x2y3 x3y3 }
             *
             * or:
             * w0[0:3] = { w0.0 w1.0 w2.0 w3.0 }
             * w1[0:3] = { w0.1 w1.1 w2.1 w3.1 }
             * w2[0:3] = { w0.2 w1.2 w2.2 w3.2 }
             * w3[0:3] = { w0.3 w1.3 w2.3 w3.3 }
             *
             * 
             */
            uint32x4x2_t wo01, wo23;
            // wo0[0:3] = { w3.0 w2.0 w3.2 w2.2 }
            // wo1[0:3] = { w3.1 w2.1 w3.3 w2.3 }
            // wo2[0:3] = { w1.2 w0.2 w1.0 w0.0 }
            // wo3[0:3] = { w1.3 w0.3 w1.1 w0.1 }
            wo01 = vtrnq_u32(w[0], w[1]);
            wo23 = vtrnq_u32(w[2], w[3]);
            
            w[0] = vcombine_u32(vget_low_u32(wo01.val[0]), vget_low_u32(wo23.val[0]));
            w[1] = vcombine_u32(vget_low_u32(wo01.val[1]), vget_low_u32(wo23.val[1]));
            vst1q_u32(fbout + (y0    ) * W + x0, w[0]);
            vst1q_u32(fbout + (y0 + 1) * W + x0, w[1]);

            w[2] = vcombine_u32(vget_high_u32(wo01.val[0]), vget_high_u32(wo23.val[0]));
            w[3] = vcombine_u32(vget_high_u32(wo01.val[1]), vget_high_u32(wo23.val[1]));
            vst1q_u32(fbout + (y0 + 2) * W + x0, w[2]);
            vst1q_u32(fbout + (y0 + 3) * W + x0, w[3]);
        }
    }

    struct timeval tv_end;
    gettimeofday(&tv_end, 0);
    long usec = (tv_end.tv_sec - tv_start.tv_sec) * 1000000 + tv_end.tv_usec - tv_start.tv_usec;
    printf("VNC updated (%d,%d) + (%d,%d) in %ld us\n", sx, sy, dx, dy, usec);
    rfbMarkRectAsModified(rfbScreen, sx, sy, sx+dx, sy+dy);
}

static QQuickView *toplevel;
SWIZZLE(void, _ZN10QQuickViewC1EP7QWindow, QQuickView *self, QWindow *win)
    printf("QQuickView %p is the top level to forward VNC events to\n", self);
    toplevel = self;
    next(self, win);
}

static Qt::KeyboardModifiers cur_modifiers = Qt::NoModifier;

static void vnc_ptr_event(int button_mask, int x, int y, struct _rfbClientRec *cl) {
    static int last_button_mask = 0;
    
    if (button_mask || last_button_mask) {
        QMouseEvent *event = new QMouseEvent(
            button_mask == last_button_mask ? QEvent::MouseMove :
            button_mask ? QEvent::MouseButtonPress
                        : QEvent::MouseButtonRelease,
            QPointF(x, y),
            Qt::LeftButton,
            button_mask ? Qt::LeftButton : Qt::NoButton,
            cur_modifiers);
        QApplication::postEvent(toplevel, event);
    }
    last_button_mask = button_mask;
}

/* from QVncClient, roughly */
#include "qvnc_keys.h"

static void vnc_kbd_event(rfbBool down, rfbKeySym key, struct _rfbClientRec *cl) {
    int unicode;
    int keycode;

    unicode = 0;
    keycode = 0;
    int i = 0;
    while (keyMap[i].keysym && !keycode) {
        if (keyMap[i].keysym == static_cast<int>(key))
            keycode = keyMap[i].keycode;
        i++;
    }

    if (keycode >= ' ' && keycode <= '~')
        unicode = keycode;

    if (!keycode) {
        if (key <= 0xff) {
            unicode = key;
            if (key >= 'a' && key <= 'z')
                keycode = Qt::Key_A + key - 'a';
            else if (key >= ' ' && key <= '~')
                keycode = Qt::Key_Space + key - ' ';
        }
    }
    
    if (keycode == Qt::Key_Shift) {
        cur_modifiers = down ? (cur_modifiers | Qt::ShiftModifier) : (cur_modifiers & ~Qt::ShiftModifier);
    } else if (keycode == Qt::Key_Control) {
        cur_modifiers = down ? (cur_modifiers | Qt::ControlModifier) : (cur_modifiers & ~Qt::ControlModifier);
    } else if (keycode == Qt::Key_Alt) {
        cur_modifiers = down ? (cur_modifiers | Qt::AltModifier) : (cur_modifiers & ~Qt::AltModifier);
    }
    
    if (keycode || unicode) {
        /* XXX: this does not fire QShortcuts like ctrl-O properly */
        QKeyEvent *event = new QKeyEvent(down ? QEvent::KeyPress : QEvent::KeyRelease, keycode, cur_modifiers, QString(unicode));
        QApplication::postEvent(toplevel, event);
    }
}

static bool _vnc_enabled = 0;
void x1plus_vnc_enable(bool enabled) {
    /* XXX: kick out any existing clients? */
    _vnc_enabled = enabled;
}

static char *_vnc_passwords[] = { NULL, NULL };
void x1plus_vnc_set_password(const char *pw) {
    if (_vnc_passwords[0]) {
        free(_vnc_passwords[0]);
        _vnc_passwords[0] = NULL;
    }
    if (pw) {
        _vnc_passwords[0] = strdup(pw);
    }
    if (rfbScreen) {
        rfbScreen->authPasswdData = _vnc_passwords[0] ? _vnc_passwords : NULL;
        rfbScreen->passwordCheck = _vnc_passwords[0] ? rfbCheckPasswordByList : NULL;
    }
}

static enum rfbNewClientAction vnc_new_client(struct _rfbClientRec *cl) {
    if (!_vnc_enabled) {
        return RFB_CLIENT_REFUSE;
    }
    if (fb_should_update_all) {
        printf("rfb is updating everything since someone connected\n");
        fb_transpose((uint32_t *)rfbScreen->frameBuffer, fb_most_recent);
    }
    return RFB_CLIENT_ACCEPT;
}


static void *vnc_thread(void *arg) {
    rfbRunEventLoop(rfbScreen, 40000, FALSE);
    return NULL;
}

static void vnc_do_flip(void *fb) {
    if (!rfbScreen) {
        rfbScreen = rfbGetScreen(0, NULL, 1280, 720, 8, 3, 4);
        rfbScreen->frameBuffer = (char *)malloc(1280 * 720 * 4);
        rfbScreen->desktopName = "X1Plus";
        rfbScreen->alwaysShared = TRUE;
        rfbScreen->ptrAddEvent = vnc_ptr_event;
        rfbScreen->kbdAddEvent = vnc_kbd_event;
        rfbScreen->newClientHook = vnc_new_client;
        rfbScreen->authPasswdData = _vnc_passwords[0] ? _vnc_passwords : NULL;
        rfbScreen->passwordCheck = _vnc_passwords[0] ? rfbCheckPasswordByList : NULL;
        rfbScreen->httpDir = strdup("/opt/vnchttp");
        rfbScreen->httpEnableProxyConnect = TRUE;
        rfbInitServer(rfbScreen); 
        /* TODO: lan access code = password */
        /* TODO: fire up novnc / vnc websocket */
        pthread_t vnc_pth;
        pthread_create(&vnc_pth, NULL, vnc_thread, NULL);
    }
    if (!rfbScreen->clientHead) {
        /* don't bother if nobody is connected */
        fb_most_recent = (uint32_t *)fb;
        fb_should_update_all = 1;
    } else {
        fb_transpose((uint32_t *)rfbScreen->frameBuffer, (uint32_t *)fb);
    }
}


SWIZZLE(int, drmIoctl, int fd, unsigned long request, void *arg)
    if (request == DRM_IOCTL_MODE_CREATE_DUMB) {
        int rv = next(fd, request, arg);
        if (rv < 0)
            return rv;

        drm_mode_create_dumb *creq = (drm_mode_create_dumb *)arg;
        for (int i = 0; i < FB_MAPS_MAX; i++) {
            if (fb_maps[i].handle)
                continue;
            fb_maps[i].handle = creq->handle;
            fb_maps[i].pitch = creq->pitch;
            fb_maps[i].size = creq->size;
            fb_maps[i].w = creq->width;
            fb_maps[i].h = creq->height;
            printf("drmIoctl mapped handle %p has pitch %d, size %d, w %d, h %d\n", fb_maps[i].handle, (int)creq->pitch, (int)creq->size, (int)creq->width, (int)creq->height);
            break;
        }
        
        return rv;
    } else if (request == DRM_IOCTL_MODE_MAP_DUMB) {
        int rv = next(fd, request, arg);
        if (rv < 0)
            return rv;
        
        drm_mode_map_dumb *mreq = (drm_mode_map_dumb *)arg;
        for (int i = 0; i < FB_MAPS_MAX; i++) {
            if (fb_maps[i].handle != mreq->handle)
                continue;
            fb_maps[i].p = mmap(0, fb_maps[i].size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, mreq->offset);
            printf("drmIoctl mapped handle %p / buf_id %p -> %p\n", fb_maps[i].handle, fb_maps[i].buf_id, fb_maps[i].p);
        }
        return rv;
    } else if (request == DRM_IOCTL_MODE_DESTROY_DUMB) {
        drm_mode_destroy_dumb *dreq = (drm_mode_destroy_dumb *)arg;
        for (int i =0; i < FB_MAPS_MAX; i++) {
            if (fb_maps[i].handle != dreq->handle)
                continue;
            if (fb_maps[i].p) {
                munmap(fb_maps[i].p, fb_maps[i].size);
            }
            fb_maps[i] = {};
        }
        return next(fd, request, arg);
    } else {
        return next(fd, request, arg);
    }
}

SWIZZLE(int, drmModeAddFB2, int fd, uint32_t width, uint32_t height, uint32_t pixel_format, const uint32_t bo_handles[4], const uint32_t pitches[4], const uint32_t offsets[4], uint32_t *buf_id, uint32_t flags)
    int rv = next(fd, width, height, pixel_format, bo_handles, pitches, offsets, buf_id, flags);
    if (rv < 0)
        return rv;

    for (int i = 0; i < FB_MAPS_MAX; i++) {
        if (fb_maps[i].handle != bo_handles[0])
            continue;
        fb_maps[i].buf_id = *buf_id;
        printf("drmModeAddFB2 mapped handle %p to buf %p\n", bo_handles[0], *buf_id);
        break;
    }

    return rv;
}

static void *last_qregion_lrs[2];
static void *qregion_want_lr = NULL;

SWIZZLE(QRegion::const_iterator, _ZNK7QRegion5beginEv, void *_this)
    QRegion::const_iterator r = next(_this);
    
    /* we want the second region call before drmModePageFlip; once we see
     * it, we don't want to do any more noise on QRegion::begin than we have
     * to, since that would certainly slow things down
     */
    if (qregion_want_lr) {
        if (__builtin_return_address(0) == qregion_want_lr) {
            lastRegion = *(QRegion *)_this;
        }
    } else {
        void *lr = __builtin_return_address(0);
        Dl_info info = {};
        int rv = dladdr(lr, &info);
        if (info.dli_fname && strstr(info.dli_fname, "qlinuxfb")) {
            printf("QRegion::begin(%p), lr = %p (%s, %s)\n", _this, lr, info.dli_fname, info.dli_sname);

            last_qregion_lrs[1] = last_qregion_lrs[0];
            last_qregion_lrs[0] = __builtin_return_address(0);

            qDebug() << *(QRegion *)_this;
            lastRegion = *(QRegion *)_this;
        }
    }
    return r;
}

SWIZZLE(int, drmModePageFlip, int fd, uint32_t crtc_id, uint32_t fb_id, uint32_t flags, void *user_data)
    if (!qregion_want_lr) {
        qregion_want_lr = last_qregion_lrs[1];
    }
    for (int i = 0; i < FB_MAPS_MAX; i++) {
        if (fb_maps[i].buf_id == fb_id) {
            vnc_do_flip(fb_maps[i].p);
        }
    }
    return next(fd, crtc_id, fb_id, flags, user_data);
}
