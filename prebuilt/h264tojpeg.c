/* heavily hacked by joshua from test_h264bsd.c */

#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>

#include "h264bsd/src/h264bsd_decoder.h"
#include "h264bsd/src/h264bsd_util.h"

#include "turbojpeg.h"

void createContentBuffer(char* contentPath, u8** pContentBuffer, size_t* pContentSize) {
  struct stat sb;
  if (stat(contentPath, &sb) == -1) {
    perror("stat failed");
    exit(1);
  }

  *pContentSize = sb.st_size;
  *pContentBuffer = (u8*)malloc(*pContentSize);
}

void loadContent(char* contentPath, u8* contentBuffer, size_t contentSize) {
  FILE *input = fopen(contentPath, "r");
  if (input == NULL) {
    perror("open failed");
    exit(1);
  }

  off_t offset = 0;
  while (offset < contentSize) {
    offset += fread(contentBuffer + offset, sizeof(u8), contentSize - offset, input);
  }

  fclose(input);
}

#include "turbojpeg.h"

char *outputPath = NULL;

void savePic(u8* picData, int width, int height, int bufw, int bufh, int picNum) {
  FILE *fd = fopen(outputPath, "w");
  if (fd == NULL) {
    perror("output file open failed");
    exit(1);
  }

  tjhandle compr = tjInitCompress();
  u8 *outbuf = NULL;
  size_t outsz;

  u8 *yData = picData;
  u8 *uData = yData + bufw * bufh;
  u8 *vData = uData + bufw * bufh / 4;
  const u8 *planes[3] = { yData, uData, vData };

  int rv = tjCompressFromYUVPlanes(compr, planes, width, NULL, height, TJSAMP_420, &outbuf, &outsz, 90, 0);
  if (rv < 0) {
    perror("tjCompressFromYUVPlanes");
    exit(1);
  }
  
  tjDestroy(compr);

  fwrite(outbuf, outsz, 1, fd);
  
  printf("wrote jpeg %d, outsz %zu\n", rv, outsz);
  fclose(fd);
}

void decodeContent (u8* contentBuffer, size_t contentSize) {
  u32 status;
  storage_t dec;
  status = h264bsdInit(&dec, HANTRO_FALSE);

  if (status != HANTRO_OK) {
    fprintf(stderr, "h264bsdInit failed\n");
    exit(1);
  }

  u8* byteStrm = contentBuffer;
  u32 readBytes;
  u32 len = contentSize;
  int numPics = 0;
  u8* pic;
  u32 picId, isIdrPic, numErrMbs;
  u32 top, left, width, height, croppingFlag;
  u32 bufw, bufh;
  int totalErrors = 0;

  while (len > 0) {
    u32 result = h264bsdDecode(&dec, byteStrm, len, 0, &readBytes);
    len -= readBytes;
    byteStrm += readBytes;

    switch (result) {
      case H264BSD_PIC_RDY:
        pic = h264bsdNextOutputPicture(&dec, &picId, &isIdrPic, &numErrMbs);
        ++numPics;
        savePic(pic, width, height, bufw, bufh, numPics);
        break;
      case H264BSD_HDRS_RDY:
        h264bsdCroppingParams(&dec, &croppingFlag, &left, &width, &top, &height);
        bufw = h264bsdPicWidth(&dec) * 16;
        bufh = h264bsdPicHeight(&dec) * 16;
        if (!croppingFlag) {
          width = bufw;
          height = bufh;
        }

        char* cropped = croppingFlag ? "(cropped) " : "";
        printf("Decoded headers. Image size %s%dx%d, orig was %dx%d.\n", cropped, width, height, h264bsdPicWidth(&dec) * 16, h264bsdPicHeight(&dec) * 16);
        break;
      case H264BSD_RDY:
        break;
      case H264BSD_ERROR:
        printf("Error\n");
        exit(1);
      case H264BSD_PARAM_SET_ERROR:
        printf("Param set error\n");
        exit(1);
    }
  }

  h264bsdShutdown(&dec);

  printf("Test file complete. %d pictures decoded.\n", numPics);
}

int main(int argc, char *argv[]) {
  int c;
  if (argc != 3) {
    fprintf(stderr, "usage: %s foo.h264 foo.jpeg\n", argv[0]);
    exit(1);
  }
  
  char *contentPath = argv[1];
  outputPath = argv[2];

  u8* contentBuffer;
  size_t contentSize;
  createContentBuffer(contentPath, &contentBuffer, &contentSize);

  loadContent(contentPath, contentBuffer, contentSize);
  decodeContent(contentBuffer, contentSize);
}