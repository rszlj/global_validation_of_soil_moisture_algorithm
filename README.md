# Global validation of the Advanced Change Detection and Short-Term Change Detections (STCDs)
This repository is for a global validaton of soil moisture retrieval algorithms

## Part I: Data preparation

### In-situ soil moisture
Ground soil moisture measurements are available at https://ismn.geo.tuwien.ac.at/en/.

A jupyter notebook (Preprocessing_ISMN_Raw_Data.ipynb) was built for the preprocessing of the raw data

The outputs include: 
- Site-specific files named as network-station including the available daily averaged soil moisutre at 0 - 5 cm of each station;
- A csv file containing the details of each station.

### SMAP data
The SMAP data is available at https://nsidc.org/data/SPL3SMP. A pyhton script can be generated automatically for batch download

Use Extract the SMAP soil moisture.ipynb to extract the soil moisutre over each station.

### Remote sensing data from Google Earth Engine (GEE)
#### Setup
An google developer account is required to access the GEE

The https://github.com/giswqs/geemap is suggested for the setup of GEE

#### Sentinel-1 and MODIS NDVI
Use Extract GEE data.ipynb to download Sentinel-1 and MODIS NDVI

### Landcover
Use Extract static auxiliary data.ipynb to download landcover from GEE

## Part II: A python version of advanced change detection and short term change detection methods
comming soon

Update on Dec. 23 2022: The author is struggling with his KPI and obviously the python version is not comming shortly. You may request a MATLAB version instead by sending to liujun.zhu@hhu.edu.cn 


## Reference
Liujun Zhu, Rui Si, Xiaoji Shen & Jeffrey P. Walker (2022) An advanced change detection method for time-series soil moisture retrieval from Sentinel-1, Remote Sensing of Environment

