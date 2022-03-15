import time
import os
import numpy as np
from threading import Thread, Event
import matplotlib
matplotlib.use('TKAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageTk
from AtlasI2C import AtlasI2C
import PySimpleGUI as sg

# ------------------------------- Matplotlib helper code --------------------------

def draw_figure(canvas, figure):
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
    return figure_canvas_agg

def make_axes(ax1, ax2, ax3, xl):
    # make the figure and axis ready for plotting
    ax1.cla()
    ax1.set_xlabel('Time')
    ax1.set_ylabel('pH')
    ax1.set_ylim([0,14])
    ax1.set_xlim(xl)
    ax1.grid()
    
    ax2.cla()
    ax2.set_xlabel('Time')
    ax2.set_ylabel('Temperature ($^\circ$C)')
    ax2.set_ylim([0,100])
    ax2.set_xlim(xl)
    ax2.grid()
    
    ax3.cla()
    ax3.set_xlabel('Time (min)')
    ax3.set_ylabel('DO (%)')
    ax3.set_ylim([0,100])
    ax3.set_xlim(xl)
    ax3.grid()
    return ax1, ax2, ax3

def make_plot(fig_agg, ax1, ax2, ax3, t, pH, RTD, DO, st):
    x = (t-st)/np.timedelta64(1,'m')
    if min(x)<0:
        xl=0
    else:
        xl=min(x)
	
    ax1, ax2, ax3 = make_axes(ax1, ax2, ax3, [xl, max(x)])
    ax1.plot(x, pH, c='purple')
    ax2.plot(x, RTD, c='red')
    ax3.plot(x, DO, c='blue')
    fig_agg.draw()
    print('Plotting chart')

# ------------------------------- GET SENSOR DATA -----------------------------------
#def get_sensor_data():
#    time.sleep(1.5)
#    pH = round(np.random.random()+7.0,3)
#    RTD = round(np.random.random()*2+40,3)
#    DO = round(np.random.random()*5+90,3)
#    return {'pH': pH, 'RTD': RTD, 'DO': DO}

def get_devices():
    device = AtlasI2C()
    device_address_list = device.list_i2c_devices()
    device_list = []
    
    for i in device_address_list:
        device.set_i2c_address(i)
        response = device.query("I")
        moduletype = response.split(",")[1] 
        #response = device.query("name,?").split(",")[1]
        name = response.split(",")[1].strip('\x00')
        device_list.append(AtlasI2C(address = i, moduletype = moduletype, name = name))
    return device_list

def get_sensor_data(device_list, delaytime, ph_temp):
    for dev in device_list:
        if dev.name == 'pH':
            dev.write('RT,'+str(ph_temp))
        else:
            dev.write("R")
    time.sleep(delaytime)

    readings = dict()

    for dev in device_list:
        #print(dev.read().split(':')[1].strip())
        #value.append(dev.read().split(':')[1].strip())
        #name.append(dev.query("I").split(',')[1])
        value = float(dev.read().split(':')[1].strip('\x00'))
        name = dev.query("I").split(',')[1].strip('\x00')
        readings[name] = value
    
    return readings

def cal_ph_7(device_list, delaytime):
    for dev in device_list:
        if dev.name == 'pH':
            dev.write('Cal,mid,7.00')
        else:
            pass
    time.sleep(delaytime)

def cal_ph_4(device_list, delaytime):
    for dev in device_list:
        if dev.name == 'pH':
            dev.write('Cal,mid,4.00')
        else:
            pass
    time.sleep(delaytime)

def cal_ph_10(device_list, delaytime):
    for dev in device_list:
        if dev.name == 'pH':
            dev.write('Cal,mid,10.00')
        else:
            pass
    time.sleep(delaytime)

def get_slope_ph(device_list, delaytime):
    # return current calibration slope of pH sensor
    slope = dict()
    for dev in device_list:
        if dev.name == 'pH':
            dev.write('Slope,?')
            time.sleep(delaytime)
            slope['acid'] = float(dev.read().split(',')[1].strip('\x00'))
            slope['base'] = float(dev.read().split(',')[2].strip('\x00'))
            slope['zero'] = float(dev.read().split(',')[3].strip('\x00'))
        else:
            pass

    return slope
    
# ------------------------------- Data handling functions -----------------------------------
def make_file(values):
    start_time=np.datetime64('now')
    fn=os.path.join(values['-DIR-'], values['-USER-']+"_"+start_time.item().strftime("%Y%m%d%H%M%S")+".txt")
    with open(fn, 'w') as f:
        f.write("BPC Data Log" + '\n')
        f.write('Start time:' '\t' + start_time.item().strftime("%Y-%m-%d %H:%M:%S")+'\n\n')
        f.write('Time' + '\t' + 'pH' + '\t' + 'RTD' + '\t' + 'DO' + '\n')
        f.close()
    return fn

def record_data(fn, t, pH, RTD, DO):
    with open(fn, 'a') as f:
        f.write(t[-1].item().strftime("%Y-%m-%d %H:%M:%S") + '\t'+ str(pH[-1]) + '\t'+ str(RTD[-1]) + '\t'+ str(DO[-1]) +'\n')
        print('Recording data')

def poll(t, pH, RTD, DO, device_list, delaytime, ph_temp):
#def poll(t, pH, RTD, DO):
        sd = get_sensor_data(device_list, delaytime, ph_temp)
        # sd = get_sensor_data()
        t.append(np.datetime64('now'))
        pH.append(sd['pH'])
        RTD.append(sd['RTD'])
        if 'DO' in sd.keys():
            DO.append(sd['DO'])
        else:
            DO.append(np.nan)

        # limit data to 1000 values
        t.pop(0)
        pH.pop(0)
        RTD.pop(0)
        DO.pop(0)
        print('Polling data')
        return t, pH, RTD, DO

def loop(window, fig_agg, ax_pH, ax_RTD, ax_DO):
        '''
        Combine all the app function callbacks in this loop function
        '''
        global t, pH, RTD, DO, st, fn, buttons, evt, device_list, delaytime, ph_temp
        while buttons['connect']:
            
            if evt.is_set():
                break
            
            t, pH, RTD, DO = poll(t, pH, RTD, DO, device_list, delaytime, ph_temp)
            # t, pH, RTD, DO = poll(t, pH, RTD, DO)
            window['-pH-'].update(pH[-1])
            window['-RTD-'].update(RTD[-1])
            window['-DO-'].update(DO[-1])
            ph_temp = RTD[-1]

            if buttons['record']:
                record_data(fn, t, pH, RTD, DO)
            
            if buttons['chart']:
                make_plot(fig_agg, ax_pH, ax_RTD, ax_DO, t, pH, RTD, DO, st)

            if buttons['phcal_7']:
                cal_ph_7(device_list, delaytime)
                time.sleep(delaytime)
                buttons['phcal_7'] = False

            if buttons['phcal_4']:
                cal_ph_4(device_list, delaytime)
                time.sleep(delaytime)
                buttons['phcal_4'] = False
            
            if buttons['phcal_10']:
                cal_ph_10(device_list, delaytime)
                time.sleep(delaytime)
                buttons['phcal_10'] = False

# ------------------------------- Select PySimpleGUI Themse -----------------------
#sg.theme('Dark Blue 3')  # please make your windows colorful
# sg.theme('DarkTanBlue')  # please make your windows colorful
sg.theme('SystemDefault')  # please make your windows colorful

# data value
dv = {'size': (8,1), 'font': ('Courier New', 12), 'text_color': 'white', 'background_color': 'grey9', 'justification': "center"}
# normal button
nb = {'button_color': ('white','midnight blue'), 'font': ('', 10)}
# red button
rb = {'button_color': ('white','red'), 'font': ('', 10)}
# green button
gb = {'button_color': ('white','green'), 'font': ('', 10)}

# ------------------------------- GUI as MAIN FUNCTION--------------------------------

def main():
    # ------------------------------- START OF APP LAYOUT-----------------------------
    # App is layout is divided into different functional frames
    
    con_elements = [[sg.Column([[ sg.Button('Connect', size=(20,1), key='-Connect-', **nb),], [sg.Text('Connection Status: '), sg.Text('Not Connected', key='-ConnectStatus-', text_color='white', background_color='red')]]),],
              [sg.Column( [[ sg.Column([[sg.Text('pH', font=('10'))], [sg.Text('NaN', **dv, key='-pH-')]], element_justification='c'), sg.Stretch(), sg.Column([[sg.Text('Temperature', font=('10'))], [sg.Text('NaN', **dv, key='-RTD-')]], element_justification='c'), sg.Stretch(),sg.Column([[sg.Text('DO', font=('10'))], [sg.Text('NaN', **dv, key='-DO-')]], element_justification='c')]])]]

    con_frame = [[sg.Frame('Connection to Devices', font=('Helvetica', 14), layout=con_elements, size=(400,200), pad=(0,0))]]
    
    # Layout for 'datalog parameters' frame
    rec_elements = [ [sg.Text('User ID: ', size=(12, 1)), sg.Input(size=(30, 1), key='-USER-')],
           [sg.Text('Select Directory: ', size=(12, 1)), sg.InputText(size=(30, 1)), sg.FolderBrowse(key='-DIR-', **nb)],
           [sg.Button('Start Recording', key='-Record-', **nb)],
           [sg.Text('Data File:', size=(10, 1)), sg.Text(key='-FileName-', size=(40, 1))]]

    rec_frame = [[sg.Frame('Select Data Recording Parameters', font=('Helvetica', 14), layout=rec_elements, size=(400,150), pad=(0,0))]]

    # Layout of 'calibration' frame
    cal_elements = [ [sg.Text('Starting the calibration will stop the data recording')],
           [sg.Button('Start pH Calibration', key='-pHCalibration-', **nb)],
           [sg.Radio('Single Point', "Cal", enable_events=True, disabled=True, key='CAL1'), sg.Radio('Two Point', "Cal", enable_events=True, disabled=True, default=True, key='CAL2'), sg.Radio('Three Point', "Cal", enable_events=True, disabled=True, key='CAL3')],
           [sg.Text('pH Buffer Required'), sg.Text("7.0 and 4.0", key='-pHSolutions-')],
           [sg.Button('Mid 7.0', key='-pHMid-', disabled=True, **nb), sg.Button('Low 4.0', key='-pHLow-', disabled=True, **nb), sg.Button('High 10.0', key='-pHHigh-', disabled=True, **nb)]]

    cal_frame = [[sg.Frame('pH Calibration', font=('Helvetica', 14), layout=cal_elements, size=(400,200), pad=(0,0))]]

    # information frame
    info_elements = [[sg.Text('Version 0.1')], [sg.Text('Developed by: M. Tahir Ashraf')], [sg.Text('Department of Green Technologies (IGT)')], [sg.Image('SDU.png', size=(100, 50), key='-IMAGE-')],]
    
    info_frame = [[sg.Frame('', layout=info_elements, size=(400,150), pad=(0,0))]]

    # Combbined layout of parameter section on left
    param_sec = sg.Column([[sg.Column(con_frame)], [sg.Column(rec_frame)], [sg.Column(cal_frame), ], [sg.Column(info_frame),]], element_justification='l', vertical_alignment='t')

    # Layout of plot section on the right
    plotsec = [[sg.Text('Chart', font=('Helvetica', 14)), sg.Stretch(), 
                sg.Button('Start Chart', key='-Chart-', **nb), sg.Button('Clear Chart', key='-ClearChart-', **rb)],
          [sg.Canvas(size=(320*0.5,240*0.5), key='-CANVAS-')]]

    ## Combine all sections into a layout
    layout = [[ param_sec, sg.VerticalSeparator(pad=None), sg.Column(plotsec) ]]
    ## make app window
    window = sg.Window('Bioprocess Process Control', layout, finalize=True, icon='SDU_Logo_2.ico', resizable=True)
    # get functional elements from app window as callable variables
    canvas_elem = window['-CANVAS-']
    canvas = canvas_elem.TKCanvas

    # ------------------------------- END OF APP LAYOUT ------------------------------------
    
    # draw the initial figure
    fig, [ax_pH, ax_RTD, ax_DO] = plt.subplots(nrows=3, ncols=1, figsize=(6,6), dpi=100)

    # add figure to axes
    ax_pH, ax_RTD, sx_DO = make_axes(ax_pH, ax_RTD, ax_DO, [0, 10])
    fig_agg=draw_figure(canvas, fig)

    # ------------------------------- EVENTS AND CALLBACKS -------------------------------
    # Arrays to hold the sensor values and in memory
    global t, pH, RTD, DO, fn, st, buttons, evt, device_list, delaytime, ph_temp
    t = list(np.array([np.datetime64('now') for i in range(1000)]))     # a dummy list to hold time data
    pH = [None]*1000                                                    # a dummy list to hold pH data from polling
    RTD = [None]*1000                                                   # a dummy list to hold RTD data from polling    
    DO = [None]*1000                                                    # a dummy list to hold DO data from polling    
    fn = ''                                                             # file name
    st = np.datetime64('now')                                           # start time
    evt = Event()                                                       # for Event logic callback
    ph_temp = 22.0                                                      # temperature compensation for pH

    # global device_list, delaytime
    device_list = get_devices()
    delaytime = device_list[0].long_timeout

    # Buttos states as bolean
    buttons = {'connect': False, 'chart': False, 'record': False, 'ph-cal': False,
                'phcal_7': True, 'phcal_4': True, 'phcal_10': False}

    while True:
        '''
        Main loop of the GUI app, which connects user inputs (test, buttons, etc.) with callback functions.
        '''
        event, values = window.read()
        print(event, values)
        if event == sg.WIN_CLOSED or event == 'Exit':
            evt.set()
            break

        elif event == '-Connect-':
            buttons['connect'] = not buttons['connect']
            window['-Connect-'].update(text='Connect' if not buttons['connect'] else 'Disconnect', button_color='white on midnight blue' if not buttons['connect'] else 'white on red')
            window['-ConnectStatus-'].update('Not Connected' if not buttons['connect'] else 'Connected', background_color='red' if not buttons['connect'] else 'green')
            if buttons['connect']:
                evt.clear()
                th1 = Thread(target=loop, args=(window, fig_agg, ax_pH, ax_RTD, ax_DO), daemon=True)
                th1.start()
            
            elif buttons['connect']==False:
                evt.set()
                #th1.join()

        elif event == '-Record-':
            if buttons['connect']==False:
                sg.popup("No Connection!", "Please make the connection to devices first")
                buttons['record'] = False

            if values['-DIR-']=='':
                sg.popup("Please select a save directory")
                buttons['record'] = False
            
            if values['-USER-']=='':
                sg.popup("Please enter a user name", "It could be an experiment name, sample name, or group name")
                buttons['record'] = False
            
            if values['-DIR-'] !='' and values['-USER-']!='' and buttons['connect']==True:
                buttons['record'] = not buttons['record']          
                
            if buttons['record']:            
                # create a file
                fn=make_file(values)
                window['-FileName-'].update(fn)
                print('File created: '+fn)
            
            window['-Record-'].update(text='Start Recording' if not buttons['record'] else 'Stop Recording', button_color='white on midnight blue' if not buttons['record'] else 'white on red')

        elif event == '-Chart-':
            if buttons['connect']==False:
                sg.popup("No Connection!", "Please make the connection to devices first")
            
            if buttons['connect']==True:
                buttons['chart'] = not buttons['chart']
            
            if buttons['chart']==True:
                st = np.datetime64('now')
                window['-ClearChart-'].update(disabled=False)

            window['-Chart-'].update(text='Start Chart' if not buttons['chart'] else 'Stop Chart', button_color='white on midnight blue' if not buttons['chart'] else 'white on red')
        
        elif event == '-ClearChart-':
            st = np.datetime64('now')
            ax_pH, ax_RTD, ax_DO = make_axes(ax_pH, ax_RTD, ax_DO, [0,10])
            fig_agg.draw()
            window['-ClearChart-'].update(disabled=True)
            buttons['chart'] = False
            
            window['-Chart-'].update(text='Start Chart' if not buttons['chart'] else 'Stop Chart', button_color='white on midnight blue' if not buttons['chart'] else 'white on red')

        # pH calibration event
        # event to start the calibration and stop the data recording
        elif event == '-pHCalibration-':
            if buttons['connect']==False:
                sg.popup("No Connection!", "Please make the connection to devices first")
            else:
                # stop recording the data
                buttons['record'] = False
                window['-Record-'].update(text='Start Recording' if not buttons['record'] else 'Stop Recording', button_color='white on midnight blue' if not buttons['record'] else 'white on red')

                # update the ph-cal status to update the button '-pHCalibration-'
                buttons['ph-cal'] = not buttons['ph-cal']
                window['-pHCalibration-'].update(text='Start Calibration' if not buttons['ph-cal'] else 'Calibration Complete', button_color='white on midnight blue' if not buttons['ph-cal'] else 'white on red')

                # enable the calibration radio and 'Cal' command buttons
                if buttons['ph-cal']:
                    window['CAL1'].update(disabled=False)
                    window['CAL2'].update(disabled=False)
                    window['CAL3'].update(disabled=False)

                    window['-pHMid-'].update(disabled=False)
                    window['-pHLow-'].update(disabled=False)
                    window['-pHHigh-'].update(disabled=True)
                
                if not buttons['ph-cal']:
                    window['CAL1'].update(disabled=True)
                    window['CAL2'].update(disabled=True)
                    window['CAL3'].update(disabled=True)

                    window['-pHMid-'].update(disabled=True)
                    window['-pHLow-'].update(disabled=True)
                    window['-pHHigh-'].update(disabled=True)
        
        elif event == 'CAL1':
            # pH calibration for single point calibration
            window['-pHSolutions-'].update("7.0")
            window['-pHMid-'].update(disabled=False)
            window['-pHLow-'].update(disabled=True)
            window['-pHHigh-'].update(disabled=True)

        elif event == 'CAL2':
            # pH calibration for two point calibration
            window['-pHSolutions-'].update("7.0 and 4.0")
            window['-pHMid-'].update(disabled=False)
            window['-pHLow-'].update(disabled=False)
            window['-pHHigh-'].update(disabled=True)

        elif event == 'CAL3':
            # pH calibration for three point calibration
            window['-pHSolutions-'].update("7.0, 4.0, and 10.0")
            window['-pHMid-'].update(disabled=False)
            window['-pHLow-'].update(disabled=False)
            window['-pHHigh-'].update(disabled=False)

        elif event == '-pHMid-':
            buttons['phcal_7'] = True

        elif event == '-pHLow-':
            buttons['phcal_4'] = True

        elif event == '-pHHigh-':
            buttons['phcal_10'] = True

        else:
            pass

    window.close()
# ------------------------------- CALL TO MAIN FUNCTION -------------------------------

if __name__ == '__main__':
    main()