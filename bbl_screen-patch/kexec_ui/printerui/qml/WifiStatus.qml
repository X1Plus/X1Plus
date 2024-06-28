import X1PlusProcess 1.0
import QtQuick 2.12
import X1PlusNative 1.0

Item {
    property string lastOutput: "" 
    property string formattedOutput: ""
    property bool running: false
    property var lanMode: false
    property var workarounds: X1PlusNative.getenv("EMULATION_WORKAROUNDS")
    signal processStateChanged(bool running)
    
    property var shellScript: [
        {
            name: "wifi_signal",
            script:  `
                while true; do
                    conn_mode=$(cat ${workarounds}/config/device/conn_mode)

                    if [ "$conn_mode" == "lan" ]; then
                        echo "lan"
                        
                    elif [ "$conn_mode" == "cloud" ]; then
                        signal_level=$(awk 'NR==3 {print $4}' "${workarounds}/proc/net/wireless" | sed -E 's/[^0-9.-]+//g; s/\.$//')
                        echo "$signal_level"
                        sleep 3
                    fi
                    sleep 5
                done

            `
        }
    ]    

    X1PlusProcess {
        id: qproc
        onReadyReadStandardOutput: {
            lastOutput = qproc.readLine().toString().trim();
            if (lastOutput == "lan"){
                lanMode = true;
                formattedOutput = "<font color='#ffb3ba'>LAN mode</font>";
                return
            } else {
                lanMode = false;
                if (lastOutput == "" || isNaN(Number(lastOutput))){
                    formattedOutput = `<font color='#fe6f47'>WiFi: n/a</font>`;
                } else {
                    formattedOutput = `<font color='#6fcc9f'>WiFi: ${lastOutput} dBm</font>`;
                }     
            }          
        }
        onErrorOccurred: {
            updateState(false);
        }
        onStarted:{
            updateState(true);
        }
        onFinished:{
            updateState(false);
            
        }
    }
    function updateState(isRunning) {
        running = isRunning;
        processStateChanged(running);
    }

    function run(name) {
        if (running) qproc.terminate();
        let w = shellScript.find(script => script.name === name);
        if (w) {
            qproc.start("/bin/bash", ["-c", w.script]);
            running = true;
        }
    }
}
