import os
import re
import pandas as pd
import glob
import numpy as np
from TimeseriesExtractor import DateTool

def Calculate_SMAP_VWC(NDVI,veg_type):
    if veg_type==1:
        stem_factor = 3.5
    else:
        stem_factor = 1
    VWC = 1.9134*NDVI**2-0.3215*NDVI+stem_factor*(NDVI-0.1)/0.9
    return VWC


def listdir_sm(network_dir):
    temp_sm_file_list=glob.glob(network_dir+'\\**\\*_sm_*.stm',recursive=True)
    sm_file_list=[]
    for file_path in temp_sm_file_list:
        temp=re.search(r'0.\d{6}_0.\d{6}',file_path)
        if temp:
            if float(temp.group().split('_')[1])<=0.051: #the depth label on the file name is 0.0508 for most us sites...
                sm_file_list.append(file_path)
    return sm_file_list


def parse_site_soil_texture(site_file):
    df=pd.read_csv(site_file,sep=';')
    if 'quantity_source_name' in df:
        temp_df=df[df['quantity_source_name']=='HWSD'] # most sites have the soil texture from HWSD 
        if len(temp_df)==0:
            temp_df=df[df['quantity_source_name']=='insitu'] # however, a few sites only have insitu values
        df=temp_df.sort_values(by=['depth_to[m]'])
        clay = float(df[df['quantity_name']=='clay fraction']['value'].iloc[0])
        sand = float(df[df['quantity_name']=='sand fraction']['value'].iloc[0])   
    else:
        clay = np.nan # for these without information of soil texture
        sand = np.nan  
    return clay/100, sand/100


def get_path_to_dir(home_dir, folder):
    target_dir = os.path.join(home_dir, folder)
    if not os.path.exists(target_dir):
        os.mkdir(target_dir)
    return target_dir


def readstm_all(file,var_name,s_time,e_time):
    # used to read sm or temperature from standard ISMN data
    with open(file) as file_in:
        lines = []
        for line in file_in:
            lines.append(line)
    if len(lines)<=10: # the the length of records is less 10, discard this file 
        return [],[]
    
    #parse header
    if (len(lines[0].split())==len(lines[1].split()))|len(lines[1].split())>=13:
        header = lines[0].split()
        network =  header[5]
        station = header[6]
        lat = float(header[7])
        lon = float(header[8])
        start_depth = int(float(header[10])*100) # cm
        end_depth = int(float(header[11])*100)
        G_flag=13
        var_flag=12
    else:
        header = lines[0].split()
        network =  header[1]
        station = header[2]
        lat = float(header[3])
        lon = float(header[4])
        start_depth = int(float(header[6])*100) # cm
        end_depth = int(float(header[7])*100)
        lines=lines[2:-1]
        G_flag=3
        var_flag=2
        
    header=pd.DataFrame({'network':[network],'station': [station],'lat':[lat],'lon':[lon],'s_depth':[start_depth],'e_depth':[end_depth]})
    timestp=[]
    obv_var=[] # the variable list, being soil moisture or temperature
    for line in lines:
        temp=line.split()
        if temp[G_flag]=='G':
            obv_var.append(float(temp[var_flag]))
            #timestp.append(temp[0]+' '+temp[1])
            timestp.append(temp[0])
    obv_var=pd.DataFrame({'time':timestp,var_name:obv_var})
    obv_var['time'] = pd.to_datetime(obv_var.time)
    obv_var.set_index('time',inplace=True)
    obv_var=obv_var.groupby(level=0).mean() # daily average
    
    df_timeframe = pd.date_range(start="2016-01-01", end="2019-12-31", freq='d').rename('time').to_frame().reset_index(drop=True)
    df_timeframe.set_index('time',inplace=True)
    date_obj = DateTool(df_timeframe.index)
    obv_var = pd.concat([date_obj.get_all_date_df(), obv_var], axis=1)
    return header, obv_var