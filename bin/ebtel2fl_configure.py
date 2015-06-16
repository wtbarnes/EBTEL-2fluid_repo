#ebtel2fl_configure.py

#Will Barnes
#7 May 2015

#Import needed modules
import numpy as np
import os
import itertools

class Configurer(object):
    
    def __init__(self,config_dictionary,root_dir,**kwargs):
        self.config_dictionary = config_dictionary
        self.root_dir = root_dir
        
        #Set up paths
        self.path_builder()
        
        if 'Hn' in kwargs:
            self.Hn = kwargs['Hn']
            
        if 'delta_q' in kwargs:
            self.delta_q = kwargs['delta_q']
            
        #check if we are using a Monte-Carlo Approach
        self.nmc_list = []
        if 'mc' in kwargs:
            #mc specifies the total number of events per Tn value
            self.mc = kwargs['mc']
        else:
            self.mc = False


    def path_builder(self,**kwargs):
        gen_path = self.config_dictionary['heat_species']+'_heating_runs/'
        if self.config_dictionary['amp_switch'] == 'uniform':
            gen_path = gen_path + 'alpha' + self.config_dictionary['amp_switch'] + '/'
        else:
            gen_path = gen_path + 'alpha' + str(np.fabs(self.config_dictionary['alpha'])) + '/'
        self.data_path = self.root_dir + gen_path + 'data/'
        self.config_path = self.root_dir + gen_path + 'config/'
        self.fn = 'ebtel2fl_L' + str(self.config_dictionary['loop_length']) + '_tn%d_tpulse' + str(2.0*self.config_dictionary['t_pulse_half']) + '_' + self.config_dictionary['solver']


    def print_xml_config(self,**kwargs):
        #Check if we have passed a filename
        #If not, pass a default filename
        if 'config_file' in kwargs:
            config_file = kwargs['config_file']
        else:
            config_file = '../config/ebtel_config.xml'

        #Open the file
        f = open(config_file,'w')

        #Print necessary header info
        f.write('<?xml version="1.0" ?>\n')
        f.write('<input>\n')

        #Loop through dictionary and print to xml file
        for key in self.config_dictionary:
            #Print tab delimiter, brackets and keyword
            f.write('\t<')
            f.write(key)
            f.write('>')
            #Check if entry is a list
            #If so print it as a list
            if isinstance(self.config_dictionary[key],list) or type(self.config_dictionary[key]).__name__ == 'ndarray':
                #Make temporary list
                temp = self.config_dictionary[key]
                #Skip to new line
                f.write('\n')
                #Begin loop over list
                for i in range(len(self.config_dictionary[key])):
                    f.write('\t\t<')
                    f.write(key+str(i))
                    f.write('>')
                    f.write(str(temp[i]))
                    f.write('</')
                    f.write(key+str(i))
                    f.write('>\n')
                #Print additional tab to preserve alignment
                f.write('\t')
            else:
                #Print value
                f.write(str(self.config_dictionary[key]))
            #Close the brackets and print newline
            f.write('</')
            f.write(key)
            f.write('>\n')

        #Close the main node of the file
        f.write('</input>')

        #Close the file
        f.close()
        
        
    def print_job_array_config(self,**kwargs):
        try:
            top_list = []
            for i in range(len(self.t_wait)):
                sub_list = []
                for j in range(self.nmc_list[i]):
                    sub_list.append([self.t_wait[i],j])
                top_list.append(sub_list)
            top_list_flattened = list(itertools.chain(*top_list))
            np.savetxt(self.config_path+'ebtel2fl_L' + str(self.config_dictionary['loop_length']) + '_tpulse' + str(2.0*self.config_dictionary['t_pulse_half']) + '_' + self.config_dictionary['solver']+'_job_array.conf',top_list_flattened,fmt='%d')
        except:
            raise ValueError("Before printing the job_array.conf file, set up the config path with path_builder and then build the t_wait and nmc_list variables by running vary_wait_time.")


    def vary_wait_time(self,tn_a,tn_b,delta_tn,**kwargs):
        """Print configuration files for varying wait-time between successive heating events"""
        #Build wait time list
        self.t_wait = np.arange(tn_a,tn_b+delta_tn,delta_tn)
        #Iterate over wait times
        for i in range(len(self.t_wait)):
            #create start time arrays and end time arrays
            self.time_arrays(self.t_wait[i])
            
            #Create directories in data and config if needed
            if not os.path.exists(self.config_path+self.fn%self.t_wait[i]):
                os.makedirs(self.config_path+self.fn%self.t_wait[i])
            if not os.path.exists(self.data_path+self.fn%self.t_wait[i]):
                os.makedirs(self.data_path+self.fn%self.t_wait[i])
            
            #Print config files for each run
            #Check if Monte-Carlo run
            if self.mc is not False:
                num_runs = self.calc_nmc()
            else:
                num_runs = 1
            self.nmc_list.append(num_runs)
            
            for j in range(num_runs):
                #build amplitude arrays
                self.amp_arrays(self.t_wait[i])
                #set name of output file
                self.config_dictionary['output_file'] = self.data_path+self.fn%self.t_wait[i]+'/'+self.fn%self.t_wait[i]+'_'+str(j)
                #print configuration files
                self.print_xml_config(config_file=self.config_path+self.fn%self.t_wait[i]+'/'+self.fn%self.t_wait[i]+'_'+str(j)+'.xml')
                
                
    def calc_nmc(self,**kwargs):
        """Calculate number of runs needed to maintain sufficiently large number of heating events"""
        return int(np.ceil(self.mc/self.config_dictionary['num_events']))


    def time_arrays(self,ti,**kwargs):
        """Create start time and end time arrays"""
        self.config_dictionary['num_events'] = int(np.ceil(self.config_dictionary['total_time']/(2.0*self.config_dictionary['t_pulse_half'] + ti)))
        self.config_dictionary['start_time_array'],self.config_dictionary['end_time_array'] = np.empty([self.config_dictionary['num_events']]),np.empty([self.config_dictionary['num_events']])
        
        for i in range(self.config_dictionary['num_events']):
            self.config_dictionary['start_time_array'][i] = i*(2.0*self.config_dictionary['t_pulse_half'] + ti)
            self.config_dictionary['end_time_array'][i] = self.config_dictionary['start_time_array'][i] + 2.0*self.config_dictionary['t_pulse_half']    
                
                
    def amp_arrays(self,ti,**kwargs):
        """Configure heating rate amplitudes"""
        #calculate uniform heating amplitude
        self.config_dictionary['h_nano'] = 2.0*self.Hn*self.config_dictionary['total_time']/(self.config_dictionary['num_events']*2.0*self.config_dictionary['t_pulse_half'])
        
        #configure power-law bounds for given heating rate to maintain specified peak temperature
        #these will work for power-law specified by 'file' or 'power_law' option
        self.config_dictionary['amp0'], self.config_dictionary['amp1'] = self.distribution_bounds(ti)
        
        #configure arrays of heating amplitudes from power_law distribution
        if self.config_dictionary['amp_switch'] == 'file':
            #calculate coefficient to convert from energy to heating rate
            if self.config_dictionary['heating_shape'] == 'triangle':
                coeff = 2.0/(2.0*self.config_dictionary['t_pulse_half']*1.0e+8*self.config_dictionary['loop_length']*self.config_dictionary['cross_sectional_loop_area'])
            elif self.config_dictionary['heating_shape'] == 'square':
                coeff = 1.0/(2.0*self.config_dictionary['t_pulse_half']*1.0e+8*self.config_dictionary['loop_length']*self.config_dictionary['cross_sectional_loop_area'])
            elif self.config_dictionary['heating_shape'] == 'gaussian':
                coeff = 1.0/(self.config_dictionary['t_pulse_half']*1.0e+8*self.config_dictionary['loop_length']*self.config_dictionary['cross_sectional_loop_area']*np.sqrt(2.0*np.pi))
                
            np.random.seed()
            x = np.random.rand(self.config_dictionary['num_events'])
            self.config_dictionary['amp_array'] = coeff*self.power_law_dist(x)
            
            
    def distribution_bounds(self,ti,**kwargs):
        """Adjust bounds on power-law distribution such that the time-averaged heating rate is preserved with varying waiting time, Tn"""
        #compute coefficient based on alpha value
        if self.config_dictionary['alpha'] < -2.0:
            coeff =  (self.config_dictionary['alpha'] + 2.0)/(self.config_dictionary['alpha'] + 1.0)*(self.delta_q**(self.config_dictionary['alpha'] + 1.0) - 1.0)/(self.delta_q**(self.config_dictionary['alpha'] + 2.0) - 1.0)
        elif self.config_dictionary['alpha'] == -2.0:
            numer = self.delta_q**(self.config_dictionary['alpha']+1.0)*(1.0 + np.log(self.delta_q)*(self.config_dictionary['alpha'] + 2.0)) - 1.0
            denom = self.delta_q**(self.config_dictionary['alpha']+2.0)*(1.0 + np.log(self.delta_q)*(self.config_dictionary['alpha'] + 1.0)) - 1.0
            coeff =  numer/denom
        else:
            coeff =  3.0/((self.delta_q - 1.0))
        
        #calculate limits    
        a0 = coeff*self.Hn*self.config_dictionary['loop_length']*1.0e+8*self.config_dictionary['cross_sectional_loop_area']*(ti + 2.0*self.config_dictionary['t_pulse_half'])
        a1 = self.delta_q*a0
        
        #return limits
        return a0,a1


    def power_law_dist(self,x):
        return ((self.config_dictionary['amp1']**(self.config_dictionary['alpha']+1) - self.config_dictionary['amp0']**(self.config_dictionary['alpha']+1))*x + self.config_dictionary['amp0']**(self.config_dictionary['alpha']+1))**(1/(self.config_dictionary['alpha']+1))
        