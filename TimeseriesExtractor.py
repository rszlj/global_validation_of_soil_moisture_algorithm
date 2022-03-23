"""Google Earth Engine Sentinel-1 Time Series Extractor class"""

import ee
import numpy as np
import os
import pandas as pd
from osgeo import osr

os.environ['HTTP_PROXY'] = 'http://127.0.0.1:41091'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:41091'
'''
set http_proxy=http://127.0.0.1:41091
set https_proxy=http://127.0.0.1:41091
earthengine authenticate
'''


class PointGeometry:
    # used for reprojection, build point with rectangle buffer
    def __init__(self, source_EPSG, target_proj):
        self.source_EPSG = source_EPSG
        self.target_proj = target_proj
        self.transform = self.build_geo_transform()

    def build_geo_transform(self):
        source = osr.SpatialReference()
        source.ImportFromEPSG(self.source_EPSG)
        target = osr.SpatialReference()
        if type(self.target_proj) == int:
            target.ImportFromEPSG(self.target_proj)
        else:
            target.ImportFromProj4(self.target_proj)
        return osr.CoordinateTransformation(source, target)

    def create_point_geo(self, x, y, buffer):
        """
        :param buffer: buffer of a point
        :param x: Longitude or x
        :param y: Latitude or y
        :return:
        """
        if type(self.target_proj) == int:
            location = self.transform.TransformPoint(y, x)
            gee_point_geometry = ee.Geometry.Point(location[0:2], 'EPSG:' + str(self.target_proj)).buffer(buffer)
        else:
            print('Error: Create_point_geo only support EPSG')
            gee_point_geometry = []
        return gee_point_geometry

    def re_project(self, x, y):
        """
        :param x: Longitude or x
        :param y: Latitude or y
        :return:
        """
        location = self.transform.TransformPoint(y, x)
        return location

    def create_polygon_geo(self, x, y, buffer):
        """
        :param buffer: buffer of a point
        :param x: Longitude or x
        :param y: Latitude or y
        :return:
        """
        if type(self.target_proj) == int:
            location = self.transform.TransformPoint(y, x)
            x = location[0]
            y = location[1]
            gee_polygon_geometry = ee.Geometry.Polygon([
                                    [x - buffer, y - buffer],
                                    [x + buffer, y - buffer],
                                    [x + buffer, y + buffer],
                                    [x - buffer, y + buffer],
                                    [x - buffer, y - buffer],
                                    ], 'EPSG:' + str(self.target_proj), True, 50, False)
        else:
            print('Error: Create_point_geo only support EPSG')
            gee_polygon_geometry = []
        return gee_polygon_geometry


class GeeS1TimeseriesExtractor:
    """Google Earth Engine Time Series Extractor class

    Parameters
    ----------
    product : str
        The Google Earth Engine product name.
    bands : list
        A list of the band names required.
    start_date : str
        The start date for the time series.
    end_date : str
        The end date for the time series.
    interpolate : str or bool, optional
        DESCRIPTION. The default is True. True for NDVI, False for Sentinel-1
    dir_name : str
        The directory where the extracted files will be stored. The
        default is ''.
    Returns
    -------
    None.
    """

    def __init__(self, product, start_date, end_date, bands, point_geometry, orbit_properties_pass='DESCENDING',
                 instrument_mode='IW', dir_name='', save_file = True):
        self.product = product
        self.bands = bands
        self.start_date = start_date
        self.end_date = end_date
        self.instrumentMode = instrument_mode
        self.orbit_properties_pass = orbit_properties_pass
        self.point_geometry = point_geometry
        self.filtered_collection = self.sentinel1_filtered_collection()
        self.image_size = self.filtered_collection.size().getInfo()
        self.save = save_file
        if self.image_size > 0:
            self.save_band_info()
            self.set_output_dir(dir_name)
            self.set_default_proj_dir()

    def sentinel1_filtered_collection(self):
        """Filters the GEE collection by date, orbit, location and observation mode

        Returns
        -------
        ee.Collection
            The filtered sentinel1 collection.
        """
        im_collection = ee.ImageCollection(self.product).filterDate(self.start_date, self.end_date)  # product and date
        im_collection = im_collection.filter(ee.Filter.eq('orbitProperties_pass', self.orbit_properties_pass))  # orbit
        im_collection = im_collection.filter(ee.Filter.eq('instrumentMode', self.instrumentMode)).select(
            self.bands)  # IW mode and bands
        im_collection = im_collection.filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
        #im_collection = im_collection.filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
        im_collection = im_collection.filterBounds(self.point_geometry)

        return im_collection

    def set_output_dir(self, dir_name):
        """Sets the extract directory

        Parameters
        ----------
        dir_name : str
            Thr name of the extract directory.
        Returns
        -------
        None.
        """
        if dir_name is None or dir_name == '':
            self.dir_name = ''
        else:
            self.dir_name = os.path.join(dir_name, '')

    def save_band_info(self):
        """Saves bands information from the GEE collection

        Returns
        -------
        None.
        """
        image_info = self.filtered_collection.first().getInfo()
        self.band_info = image_info['bands']
        data_type = self.band_info[0]['data_type']  # Assumes all bands have the same data type
        self.data_type = 'Int64' if data_type['precision'] == 'int' else np.float64

    def _int_data(self):
        return self.data_type == 'Int64'

    def set_default_proj_dir(self):
        """Sets the default extract projection and scale

        Sets the extract projection and scale to the collection's
        native projection and scale.
        Returns
        -------
        None.
        """
        band = self.band_info[0]  # Assumes all bands have the same proj/scale
        self.projection = band['crs']
        self.scale = abs(band['crs_transform'][0])  # crs_tranform is [+/-scale, 0, x, 0 , +/-scale, y]

    def set_proj_scale(self, proj, scale):
        """Sets the required projection and scale for the extract

        Parameters
        ----------
        proj : str
            The required projection.
        scale : float
            The required scale.
        Returns
        -------
        None.
        """
        self.projection = proj
        self.scale = scale

    def download_data(self):
        """Download the GEE data for a location

        Downloads the GEE data for a location, converts it to a data
        frame and gap fills if required.

        Parameters
        ----------
        location : Pandas series
            A Pandas series containing the location ``Longitude`` and
            ``Latitude``.
        Returns
        -------
        bands_df : Pandas data frame
            A data frame. The columns are the bands and the index is
            the dates.
        """

        data = self.filtered_collection.getRegion(
            self.point_geometry, self.scale, self.projection).getInfo()
        data_df = pd.DataFrame(data[1:], columns=data[0])
        #self.last_longitude = data_df.longitude[0]
        #self.last_latitude = data_df.latitude[0]
        bands_index = pd.DatetimeIndex(pd.to_datetime(data_df.time, unit='ms').dt.date)
        data_df = data_df.set_index(bands_index).rename_axis(index='time').sort_index()
        bands_df = data_df[self.bands]
        bands_df = bands_df.groupby(level=0).mean()
        fname_df = data_df['id'] # parse the relative orbit and platform
        fname_df = fname_df[~fname_df.index.duplicated(keep='first')]
        platform_orbit_df = [self.parse_S1_platform_orbit(fname) for fname in fname_df]
        platform_orbit_df = pd.DataFrame(platform_orbit_df, columns=['platform','relative_orbit'])
        platform_orbit_df.index = fname_df.index
        bands_df = pd.concat([bands_df, platform_orbit_df], axis=1)
        if self.orbit_properties_pass == 'ASCENDING':
            bands_df['orbit_pass'] = 0  # use 0 to represent the ASCENDING
        else:
            bands_df['orbit_pass'] = 1  # use 1 to represent the DESCENDING

        if self._int_data():
            bands_df[self.bands] = bands_df[self.bands].round().astype(self.data_type)

        return bands_df

    def get_and_save_data(self, site_name):
        """Get and save the GEE data for a location

        Checks if data has already been extracted for the location (a
        file called ``<Site>.csv`` already exists). If the file exists,
        it is read into a data frame and returned. If it doesn't exist,
        the data for the location will be downloaded, saved to
        ``<Site>.csv`` and the data frame returned.
        Parameters
        ----------
        location : Pandas series
            A Pandas series containing the ``Site`` name and location
            ``Longitude`` and ``Latitude``.
        Returns
        -------
        point_df : Pands data frame
            A data frame. The columns are the bands and the index is
            the dates.
        """
        file_name = f'{self.dir_name}{site_name}.csv'
        '''
        try:  # If we already have the location data, read it
            dtypes = {band: self.data_type for band in self.bands}
            point_df = pd.read_csv(file_name, index_col="id", parse_dates=True, dtype=dtypes)
        except:  # Otherwise extract it from GEE
            #print(f'Extracting data for {site_name} ')
        '''
        point_df = self.download_data()
        date_obj = DateTool(point_df.index)
        point_df = pd.concat([date_obj.get_all_date_df(), point_df], axis=1)
        if self.save:
            point_df.to_csv(file_name)
        return point_df

    def parse_S1_platform_orbit(self, fname):
        platform = fname[2]
        obs_orbit = int(fname.split('_')[6])
        if platform == 'A':
            rel_orbit = (obs_orbit - 73) % 175 + 1
            platform = 0  # use 0 to represent the Sentinel-1A
        else:
            rel_orbit = (obs_orbit - 27) % 175 + 1  # Sentinel-1B
            platform = -1  # use -1 to represent the Sentinel-1B
        return platform, rel_orbit


class GeeTimeseriesExtractor:
    """Google Earth Engine Time Series Extractor class

    Parameters
    ----------
    product : str
        The Google Earth Engine product name.
    bands : list
        A list of the band names required.
    start_date : str
        The start date for the time series.
    end_date : str
        The end date for the time series.
    freq : str, optional
        The frequency of time series entries. The default is '1D' for
        daily entries.
    gap_fill : str or bool, optional
        DESCRIPTION. The default is True.
    max_gap : int, optional
        The maximum size of gap that will be filled. Filling is done in
        both directions, so the maximum actual size filled is
        ``2 * max_gap``. If None, there if no limit on the gap size.
        The default is None.
    dir_name : str
        The directory where the extracted files will be stored. The
        default is ''.
    Returns
    -------
    None.
    """

    def __init__(self, product, bands, start_date, end_date, dir_name='', save_file=True):
        self.product = product
        self.bands = bands
        self.start_date = start_date
        self.end_date = end_date
        self.collection = ee.ImageCollection(product).select(bands)
        # self.set_date_range(start_date, end_date, freq, gap_fill, max_gap)
        self.save_band_info()
        self.set_output_dir(dir_name)
        self.set_default_proj_dir()
        self.save = save_file

    def set_date_range(self, start_date, end_date, freq='1D', gap_fill=True, max_gap=None):
        """Sets the date range for the extracts

        Parameters
        ----------
        start_date : str
            The start date for the time series.
        end_date : str
            The end date for the time series.
        freq : str, optional
            The frequency of time series entries. The default is '1D'
            for daily entries.
        gap_fill : str or bool, optional
            DESCRIPTION. The default is True.
        max_gap : int, optional
            The maximum size of gap that will be filled. Filling is
            done in both directions, so the maximum actual size filled
            is ``2 * max_gap``. If None, there if no limit on the gap
            size. The default is None.
        Returns
        -------
        None.
        """
        self.start_date = start_date
        self.end_date = end_date
        if gap_fill:
            date_range = pd.date_range(start_date, end_date, freq=freq, closed="left")
            self.days = pd.Series(date_range, name="id")
            self.fill = pd.DataFrame(date_range, columns=["id"])
            self.gap_fill = gap_fill
            self.max_gap = max_gap
        else:
            self.gap_fill = False

    def filtered_collection(self):
        """Filters the GEE collection by date

        Returns
        -------
        ee.Collection
            The filtered GEE collection.
        """
        return self.collection.filterDate(self.start_date, self.end_date)

    def set_output_dir(self, dir_name):
        """Sets the extract directory

        Parameters
        ----------
        dir_name : str
            Thr name of the extract directory.
        Returns
        -------
        None.
        """
        if dir_name is None or dir_name == '':
            self.dir_name = ''
        else:
            self.dir_name = os.path.join(dir_name, '')

    def save_band_info(self):
        """Saves bands information from the GEE collection

        Returns
        -------
        None.
        """
        image_info = self.filtered_collection().first().getInfo()
        self.band_info = image_info['bands']
        data_type = self.band_info[0]['data_type']  # Assumes all bands have the same data type
        self.data_type = 'Int64' if data_type['precision'] == 'int' else np.float

    def _int_data(self):
        return self.data_type == 'Int64'

    def set_default_proj_dir(self):
        """Sets the default extract projection and scale

        Sets the extract projection and scale to the collection's
        native projection and scale.
        Returns
        -------
        None.
        """
        band = self.band_info[0]  # Assumes all bands have the same proj/scale
        self.projection = band['crs']
        self.scale = abs(band['crs_transform'][0])  # crs_tranform is [+/-scale, 0, x, 0 , +/-scale, y]

    def set_proj_scale(self, proj, scale):
        """Sets the required projection and scale for the extract

        Parameters
        ----------
        proj : str
            The required projection.
        scale : float
            The required scale.
        Returns
        -------
        None.
        """
        self.projection = proj
        self.scale = scale

    def download_data(self, point_geo):
        """Download the GEE data for a location

        Downloads the GEE data for a location, converts it to a data
        frame and gap fills if required.

        Parameters
        ----------
        location : Pandas series
            A Pandas series containing the location ``Longitude`` and
            ``Latitude``.
        Returns
        -------
        bands_df : Pandas data frame
            A data frame. The columns are the bands and the index is
            the dates.
        """
        #point_geo = ee.Geometry.Point(location[0:2], self.projection)
        data = self.filtered_collection().getRegion(
            point_geo, self.scale, self.projection).getInfo()
        data_df = pd.DataFrame(data[1:], columns=data[0])
        #self.last_longitude = data_df.longitude[0]
        #self.last_latitude = data_df.latitude[0]
        bands_index = pd.DatetimeIndex(pd.to_datetime(data_df.time, unit='ms').dt.date)
        bands_df = data_df[self.bands].set_index(bands_index).rename_axis(index='time').sort_index()
        date_obj = DateTool(bands_df.index)
        bands_df = pd.concat([date_obj.get_all_date_df(), bands_df], axis=1)
        #bands_df = bands_df.groupby(level=0).mean()
        '''
        if self.gap_fill:
            bands_df = bands_df.merge(self.days, how="right",
                                      left_index=True, right_on='id').set_index('id')
            method = 'linear' if self.gap_fill == True else self.gap_fill
            bands_df = bands_df[self.bands].interpolate(axis=0, method=method, limit=self.max_gap,
                                                        limit_direction="both")
        '''
        if self._int_data():
            bands_df = bands_df.round().astype(self.data_type)
        return bands_df

    def get_and_save_data(self, location, site_name):
        """Get and save the GEE data for a location

        Checks if data has already been extracted for the location (a
        file called ``<Site>.csv`` already exists). If the file exists,
        it is read into a data frame and returned. If it doesn't exist,
        the data for the location will be downloaded, saved to
        ``<Site>.csv`` and the data frame returned.
        Parameters
        ----------
        location : Pandas series
            A Pandas series containing the ``Site`` name and location
            ``Longitude`` and ``Latitude``.
        Returns
        -------
        point_df : Pands data frame
            A data frame. The columns are the bands and the index is
            the dates.
        """
        file_name = f'{self.dir_name}{site_name}.csv'
        try:  # If we already have the location data, read it
            dtypes = {band: self.data_type for band in self.bands}
            point_df = pd.read_csv(file_name, index_col="id", parse_dates=True, dtype=dtypes)
        except:  # Otherwise extract it from GEE
            print(f'Extracting data for {site_name}')
            point_df = self.download_data(location)
            if self.save:
                point_df.to_csv(file_name)
        return point_df


class DateTool:
    def __init__(self, time_stamp_list):
        self.time_stamp_list = time_stamp_list

    def get_all_date_df(self):
        DoY = self.time_stamp_list.day_of_year
        Excel_day = self.date2excel_day()
        date_df = {'Excel_day': Excel_day, 'DoY': DoY}
        date_df = pd.DataFrame(date_df, index=self.time_stamp_list)
        return date_df

    def date2excel_day(self):
        temp = self.time_stamp_list - pd.to_datetime("1900-1-1")
        excel_day = temp.days + 2
        return excel_day