import numpy as np
import yapic_io.image_importers as ip
import logging
import os
import glob
from yapic_io.utils import get_template_meshgrid, add_to_filename
from functools import lru_cache
from yapic_io.connector import Connector
from pprint import pprint
logger = logging.getLogger(os.path.basename(__file__))


class TiffConnector(Connector):
    '''
    implementation of Connector for normal sized tiff images
    and corresponding label masks in tiff format.
    
    Initiate a new TiffConnector as follows:

    >>> from yapic_io.tiff_connector import TiffConnector
    >>> pixel_image_dir = 'yapic_io/test_data/tiffconnector_1/im/*.tif'
    >>> label_image_dir = 'yapic_io/test_data/tiffconnector_1/labels/*.tif'
    >>> t = TiffConnector(pixel_image_dir, label_image_dir)
    >>> print(t)
    Connector_tiff object
    image filepath: yapic_io/test_data/tiffconnector_1/im/*.tif
    label filepath: yapic_io/test_data/tiffconnector_1/labels/*.tif
    <BLANKLINE>
    '''
    def __init__(self, img_filepath, label_filepath, savepath=None):
        img_filepath   = os.path.normpath(os.path.expanduser(img_filepath))
        label_filepath = os.path.normpath(os.path.expanduser(label_filepath))

        if os.path.isdir(img_filepath):
            img_filepath = os.path.join(img_filepath, '*.tif')
        if os.path.isdir(label_filepath):
            label_filepath = os.path.join(label_filepath, '*.tif')

        self.img_path, self.img_filemask = os.path.split(img_filepath)
        self.label_path, self.label_filemask = os.path.split(label_filepath)
        self.savepath = savepath #path for probability maps

        self.load_img_filenames()
        self.load_label_filenames()
        self.check_labelmat_dimensions()


    def __repr__(self):

        infostring = \
            'Connector_tiff object\n' \
            'image filepath: %s\n' \
            'label filepath: %s\n' \
             % (os.path.join(self.img_path, self.img_filemask)\
                , os.path.join(self.label_path, self.label_filemask))

        return infostring


    def get_image_count(self):
        
        if self.filenames is None:
            return 0
        
        return len(self.filenames)


    
    def put_template(self, pixels, pos_zxy, image_nr, label_value):
        
        if not len(pos_zxy) == 3:
            raise ValueError('pos_zxy has not length 3: %s' % str(pos_zxy))

        if not len(pixels.shape) == 3:
            raise ValueError('''probability map pixel template
             must have 3 dimensions (z,x,y), but has %s : 
             pixels shape is %s''' % \
             (str(len(pixels.shape)), str(pixels.shape)))

        out_path = self.init_probmap_image(image_nr, label_value)

        logger.info('try to add new pixels to  image %s', out_path)
        return ip.add_vals_to_tiff_image(out_path, pos_zxy, pixels)


    def init_probmap_image(self, image_nr, label_value, overwrite=False):
        out_path = self.get_probmap_path(image_nr, label_value)
        _, z_shape, x_shape, y_shape = self.load_img_dimensions(image_nr)
        
        if not os.path.isfile(out_path) or overwrite:
            ip.init_empty_tiff_image(out_path, x_shape, y_shape, z_size=z_shape)
            logger.info('initialize a new probmap image: %s', out_path)
        return out_path        

    def get_probmap_path(self, image_nr, label_value):
        if self.savepath is None:
            raise ValueError('savepath not set')
        image_filename = self.filenames[image_nr][0]
        probmap_filename = add_to_filename(image_filename,\
                     'class_' + str(label_value))
        return os.path.join(self.savepath, probmap_filename)


            

    def get_template(self, image_nr=None, pos=None, size=None):

        im = self.load_image(image_nr)
        mesh = get_template_meshgrid(im.shape, pos, size)

        return(im[mesh])


    def load_img_dimensions(self, image_nr):
        '''
        returns dimensions of the dataset.
        dims is a 4-element-tuple:
        
        :param image_nr: index of image
        :returns (nr_channels, nr_zslices, nr_x, nr_y)

        '''        

        if not self.is_valid_image_nr(image_nr):
            return False          

        path = os.path.join(self.img_path, self.filenames[image_nr][0])
        return ip.get_tiff_image_dimensions(path) 

    def load_labelmat_dimensions(self, image_nr):
        '''
        returns dimensions of the label image.
        dims is a 4-element-tuple:
        
        :param image_nr: index of image
        :returns (nr_channels, nr_zslices, nr_x, nr_y)

        '''        

        if not self.is_valid_image_nr(image_nr):
            return False          

        if self.exists_label_for_img(image_nr):
            path = os.path.join(self.label_path, self.filenames[image_nr][1])
            return ip.get_tiff_image_dimensions(path)               
    

    def check_labelmat_dimensions(self):
        '''
        check if label mat dimensions fit to image dimensions, i.e.
        everything identical except nr of channels (label mat always 1)
        '''
        logger.info('labelmat dimensions check')
        nr_channels = []
        for image_nr in list(range(self.get_image_count())):
            im_dim = self.load_img_dimensions(image_nr)
            label_dim = self.load_labelmat_dimensions(image_nr)
            

            if label_dim is None:
                logger.info('check image nr %s: ok (no labelmat found) ', image_nr)
            else:
                nr_channels.append(label_dim[0])
                logger.info('found %s label channel(s)', nr_channels[-1])
                #pprint(self.filenames)
                #logger.info('labeldim: %s', label_dim)
                #logger.info('imdim: %s ', im_dim)
                if label_dim[1:] == im_dim[1:]:
                    logger.info('check image nr %s: ok ', image_nr)
                else:
                    raise ValueError('check image nr %s: dims do not match ' % str(image_nr))   
        if len(set(nr_channels))>1:
            raise ValueError('nr of channels not consitent in input data, found following nr of labelmask channels: %s' , str(set(nr_channels)))            

    @lru_cache(maxsize = 20)
    def load_image(self, image_nr):
        if not self.is_valid_image_nr(image_nr):
            return None      
        path = os.path.join(self.img_path, self.filenames[image_nr][0])
        return ip.import_tiff_image(path)    


    def exists_label_for_img(self, image_nr):
        if not self.is_valid_image_nr(image_nr):
            return None      
        if self.filenames[image_nr][1] is None:
            return False
        return True    


    @lru_cache(maxsize = 20)    
    def load_label_matrix(self, image_nr):
        
        if not self.is_valid_image_nr(image_nr):
            return None      

        label_filename = self.filenames[image_nr][1]      
        
        if label_filename is None:
            logger.warning('no label matrix file found for image file %s', str(image_nr))    
            return None
        
        path = os.path.join(self.label_path, label_filename)
        logger.info('try loading labelmat %s',path)
        return ip.import_tiff_image(path)    


    def get_labelvalues_for_im(self, image_nr):
        mat = self.load_label_matrix(image_nr)
        if mat is None:
            return None
        values =  np.unique(mat)
        values = values[values!=0]
        values.sort()
        return list(values)


    @lru_cache(maxsize = 500)
    def get_label_coordinates(self, image_nr):
        ''''
        returns label coordinates as dict in following format:
        channel has always value 0!! This value is just kept for consitency in 
        dimensions with corresponding pixel data 

        {
            label_nr1 : [(channel, z, x, y), (channel, z, x, y) ...],
            label_nr2 : [(channel, z, x, y), (channel, z, x, y) ...],
            ...
        }


        :param image_nr: index of image
        :returns: dict of label coordinates
    
        '''

        mat = self.load_label_matrix(image_nr)
        labels = self.get_labelvalues_for_im(image_nr)
        if labels is None:
            #if no labelmatrix available
            return None
        
        label_coor = {}
        for label in labels:
            coors = np.array(np.where(mat==label))
            coor_list = [tuple(coors[:,i]) for i in list(range(coors.shape[1]))]
            label_coor[label] = coor_list#np.array(np.where(mat==label))
        
        return label_coor    


    def is_valid_image_nr(self, image_nr):
        count = self.get_image_count()
        
        error_msg = \
        'wrong image number. image numbers in range 0 to %s' % str(count-1)
        
        if image_nr not in list(range(count)):
            logger.error(error_msg)
            return False

        return True          


    def load_label_filenames(self, mode='identical'):
        if self.filenames is None:
            return

        if mode == 'identical':
            #if label filenames should match exactly with img filenames
            for name_tuple in self.filenames:
                img_filename = name_tuple[0]   
                label_path = os.path.join(self.label_path, img_filename)
                if os.path.isfile(label_path): #if label file exists for image file
                    name_tuple[1] = img_filename


    def load_img_filenames(self):
        '''
        find all tiff images in specified folder (self.img_path, self.img_filemask)
        '''
        img_filenames = glob.glob(os.path.join(self.img_path, self.img_filemask))
        
        filenames = [[os.path.split(filename)[1], None] for filename in img_filenames]
        if len(filenames) == 0:
            self.filenames = None
            return
        self.filenames = filenames
        return True 

