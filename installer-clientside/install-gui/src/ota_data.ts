type modversion = { url: string; sig: string; version: string; }
type ota = { url: string; ota: string; rk1126: modversion; mc07?: modversion; th07?: modversion; th09?: modversion; }

const otas : { [version: string]: ota } = {
    "01.05.01.00": {
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.05.01.00/product/ota-v01.05.01.00-20230425204025.json.sig",
        "ota": "ota-v01.05.01.00-20230425204025.json",
        "mc07": {
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.05.01.00/product/mc_rev7-firmware-v00.00.14.33-20230413203744_product.bin.sig",
            "sig": "e118312141b0bf238f520a5974b1b1a7",
            "version": "00.00.14.33"
        },
        "rk1126": {
            "sig": "ead071558facca18e18fe33d9103cb75",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.05.01.00/product/update-v00.00.19.15-20230423131316_product.img.zip.sig",
            "version": "00.00.19.15"
        },
        "th07": {
            "sig": "2b98f8ac7f6d568c0bb8cb22d7e3a79b",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.05.01.00/product/th_rev7-firmware-v00.00.04.99-20230208172143_product.bin.sig",
            "version": "00.00.04.99"
        },
        "th09": {
            "sig": "c5f7b9cfd0fcfc466a58cb4f0f28dca3",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.05.01.00/product/th_rev9-firmware-v00.00.04.99-20230208172243_product.bin.sig",
            "version": "00.00.04.99"
        }
    },
    "01.03.00.00": {
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.03.00.00/product/ota-v01.03.00.00-20221216230742.json.sig",
        "ota": "ota-v01.03.00.00-20221216230742.json",
        "mc07": {
            "sig": "21c6a7b667449993088cdca2701c4a2c",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.03.00.00/product/mc_rev7-firmware-v00.00.12.63-20221215143142_product.bin.sig",
            "version": "00.00.12.63"
        },
        "rk1126": {
            "sig": "7ff4e2f4802a7eb7a190bdd35eddd658",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.03.00.00/product/update-v00.00.16.35-20221216210511_product.img.zip.sig",
            "version": "00.00.16.35"
        },
        "th07": {
            "sig": "98fa79ea8b2de90dcc192276c1f80b2a",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.03.00.00/product/th_rev7-firmware-v00.00.04.53-20221215143640_product.bin.sig",
            "version": "00.00.04.53"
        },
        "th09": {
            "sig": "131b4e73f0077c62094ed4fd402101a9",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.03.00.00/product/th_rev9-firmware-v00.00.04.53-20221215143750_product.bin.sig",
            "version": "00.00.04.53"
        }
    },
    "01.06.03.00": {
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.06.03.00/product/ota-v01.06.03.00-20230821143043.json.sig",
        "ota": "ota-v01.06.03.00-20230821143043.json",
        "mc07": {
            "sig": "70c83a5e5c572609b2f360ef8617471d",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.06.03.00/product/mc_rev7-firmware-v00.00.16.63-20230808092049_product.bin.sig",
            "version": "00.00.16.63"
        },
        "rk1126": {
            "sig": "5a679b1b2351398cd45ee729fe42b588",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.06.03.00/product/update-v00.00.22.23-20230817181430_product.img.zip.sig",
            "version": "00.00.22.23"
        },
        "th07": {
            "sig": "d3fa652d45150b431a678ac64dc13e82",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.06.03.00/product/th_rev7-firmware-v00.00.05.83-20230703150458_product.bin.sig",
            "version": "00.00.05.83"
        },
        "th09": {
            "sig": "4bbc6306b6452f86d692eb2f41c06cb2",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.06.03.00/product/th_rev9-firmware-v00.00.05.83-20230703150621_product.bin.sig",
            "version": "00.00.05.83"
        }
    },
    "01.06.05.01": {
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.06.05.01/product/ota-v01.06.05.01-20230922193137.json.sig",
        "ota": "ota-v01.06.05.01-20230922193137.json",
        "mc07": {
            "sig": "3b08efaca8117147dbb7da7b7a54bda1",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.06.05.01/product/mc_rev7-firmware-v00.00.16.68-20230921175046_product.bin.sig",
            "version": "00.00.16.68"
        },
        "rk1126": {
            "sig": "665843b698036319cbe9a60078b5182d",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.06.05.01/product/update-v00.00.24.13-20230922180718_product.img.zip.sig",
            "version": "00.00.24.13"
        },
        "th07": {
            "sig": "d3fa652d45150b431a678ac64dc13e82",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.06.05.01/product/th_rev7-firmware-v00.00.05.83-20230703150458_product.bin.sig",
            "version": "00.00.05.83"
        },
        "th09": {
            "sig": "4bbc6306b6452f86d692eb2f41c06cb2",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.06.05.01/product/th_rev9-firmware-v00.00.05.83-20230703150621_product.bin.sig",
            "version": "00.00.05.83"
        }
    },
    "01.04.01.00": {
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.04.01.00/product/ota-v01.04.01.00-20230227162230.json.sig",
        "ota": "ota-v01.04.01.00-20230227162230.json",
        "mc07": {
            "sig": "fad46c4c2ac35db9156e78740ffb782b",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.04.01.00/product/mc_rev7-firmware-v00.00.13.28-20230217100640_product.bin.sig",
            "version": "00.00.13.28"
        },
        "rk1126": {
            "sig": "0f021ea2b492637d47f32921ccf549e7",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.04.01.00/product/update-v00.00.17.74-20230227093636_product.img.zip.sig",
            "version": "00.00.17.74"
        },
        "th07": {
            "sig": "2b98f8ac7f6d568c0bb8cb22d7e3a79b",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.04.01.00/product/th_rev7-firmware-v00.00.04.99-20230208172143_product.bin.sig",
            "version": "00.00.04.99"
        },
        "th09": {
            "sig": "c5f7b9cfd0fcfc466a58cb4f0f28dca3",
            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.04.01.00/product/th_rev9-firmware-v00.00.04.99-20230208172243_product.bin.sig",
            "version": "00.00.04.99"
        }
    },
    
"01.07.00.00": {
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.07.00.00/product/3b63468a6f/ota-v01.07.00.00-20231222194536.json.sig",
        "ota": "ota-v01.07.00.00-20231211111947.json",
        "mc07": {
        "sig": "6c582ad4f3fb377262372da2fc36683b",
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.07.00.00/product/3b63468a6f/mc_rev7-firmware-v00.00.22.33-20231120144837_product.bin.sig",
        "version": "00.00.22.33"
    },
    "rk1126": {
        "sig": "c13453b8e144c73ba6f8eee76a639b3c",
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.07.00.00/product/3b63468a6f/update-v00.00.28.36-20231207153519_product.img.zip.sig",
        "version": "00.00.28.36"
    },
    "th07": {
        "sig": "20eacbc29a81fa42daf93a8693cbc113",
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.07.00.00/product/3b63468a6f/th_rev7-firmware-v00.00.07.12-20231031102713_product.bin.sig",
        "version": "00.00.07.12"
    },
    "th09": {
        "sig": "7549a5096c530a1ba43e92f4ad0e3261",
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.07.00.00/product/3b63468a6f/th_rev9-firmware-v00.00.07.12-20231031102810_product.bin.sig",
        "version": "00.00.07.12"
        }
    },
    "01.07.01.00": {
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.07.01.00/product/c6c10c944a/ota-v01.07.01.00-20231222194536.json.sig",
        "ota": "ota-v01.07.01.00-20231222194536.json",
        "mc07": {
        "sig": "6c582ad4f3fb377262372da2fc36683b",
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.07.01.00/product/c6c10c944a/mc_rev7-firmware-v00.00.22.33-20231120144837_product.bin.sig",
        "version": "00.00.22.33"
        },
        "rk1126": {
        "sig": "8eb06ccaaf6a5521c034c2633b46fb66",
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.07.01.00/product/c6c10c944a/update-v00.00.28.44-20231222033833_product.img.zip.sig",
        "version": "00.00.28.44"
        },
        "th07": {
            "sig": "20eacbc29a81fa42daf93a8693cbc113",
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.07.01.00/product/c6c10c944a/th_rev7-firmware-v00.00.07.12-20231031102713_product.bin.sig",
        "version": "00.00.07.12"
        },
        "th09": {
            "sig": "7549a5096c530a1ba43e92f4ad0e3261",
        "url": "https://public-cdn.bambulab.com/upgrade/device/BL-P001/01.07.01.00/product/c6c10c944a/th_rev9-firmware-v00.00.07.12-20231031102810_product.bin.sig",
        "version": "00.00.07.12"
        }
    }  
};




export default otas;
