#Name: ebtel2fl_compare_dem.py
#Author: Will Barnes
#Date: 21 February 2014

#Import needed modules to plot non-interactively
import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt

def find_temp_bounds(temp,dem,delta):
    """Calculate corresponding temperature bounds for DEM threshold value.
    
    Arguments:
    temp -- log of temperature bin
    dem -- log of coronal DEM value 
    delta -- orders of magnitude below the DEM peak to begin the integration
    """
    
    #Find peak DEM value
    dem_max = np.max(dem)
    
    #Find temperature for peak DEM value
    i_dem_max = np.argmax(dem)
    temp_dem_max = temp[i_dem_max]
    
    #Calculate bounds on the integration (+/- two orders of magnitude of the peak)
    #If the DEM value is +/-Inf, find the closest value that =! +/-Inf
    dem_bound = dem_max - delta
    
    #Create cool and hot DEM and temperature arrays
    dem_hot = dem[i_dem_max:-1]
    temp_hot = temp[i_dem_max:-1]
    dem_cool = dem[0:i_dem_max]
    temp_cool = dem[0:i_dem_max]
    
    #Find the indices for hot and cool bounds
    i_dem_hot = np.where(dem_hot > dem_bound)[0][-1] + 1
    i_dem_cool = np.where(dem_cool > dem_bound)[0][0] - 1
    
    #Make sure that the indices do not correspond to 'Inf' DEM values
    found_cool_bound = False
    found_hot_bound = False
    
    while found_cool_bound == False or found_hot_bound == False:
        if found_cool_bound == False:
            if np.isinf(dem_cool[i_dem_cool]):
                i_dem_cool = i_dem_cool + 1
            else:
                temp_bound_cool = temp_cool[i_dem_cool]
                found_cool_bound = True
                
        if found_hot_bound == False:
            if np.isinf(dem_hot[i_dem_hot]):
                i_dem_hot = i_dem_hot - 1
            else:
                temp_bound_hot = temp_hot[i_dem_hot]
                found_hot_bound = True
                
    #Return the corresponding indices
    return {'i_cool':i_dem_cool,'i_max':i_dem_max,'i_hot':(i_dem_max+i_dem_hot)}

def dem_shoulder_compare_fit(temp,dem,delta):
    """Compute coolward and hotward slope of DEM curve for a linear fit.
    
    Arguments:
    temp -- log of temperature bin
    dem -- log of coronal DEM value 
    delta -- orders of magnitude below the DEM peak to begin the integration
    
    """
    
    #Find the corresponding temperature bounds
    dict_bounds = find_temp_bounds(temp,dem,delta)
    
    #Calculate the slope
    #Hot shoulder
    a_hotward = (dem[dict_bounds['i_hot']] - dem[dict_bounds['i_max']])/(temp[dict_bounds['i_hot']] - temp[dict_bounds['i_max']])
    #Cool shoulder
    a_coolward = (dem[dict_bounds['i_max']] - dem[dict_bounds['i_cool']])/(temp[dict_bounds['i_max']] - temp[dict_bounds['i_cool']])
    
    #Return the hot and cool slopes
    return {'a_hot':a_hotward,'a_cool':a_coolward}
    
    

def dem_shoulder_compare_integrate(temp,dem,delta):
    """Compute integral of hot and cold shoulder and calculate ratio to provide quantitative measure of hot DEM component.
    
    Arguments:
    temp -- log of temperature bin
    dem -- log of coronal DEM value 
    delta -- orders of magnitude below the DEM peak to begin the integration
    
    """
    #Find the corresponding temperature bounds
    dict_bounds = find_temp_bounds(temp,dem,delta)
                
    #Now that we have the bounds, do the integration
    #Hot shoulder 
    hot_shoulder = np.trapz(dem[dict_bounds['i_max']:dict_bounds['i_hot']],x=temp[dict_bounds['i_max']:dict_bounds['i_hot']])
    #Total
    total_shoulder = np.trapz(dem[dict_bounds['i_cool']:dict_bounds['i_hot']],x=temp[dict_bounds['i_cool']:dict_bounds['i_hot']])
    #Compute the ratio
    hot_shoulder_strength = hot_shoulder/total_shoulder
    
    return hot_shoulder_strength


def plot_ebtel_dem_compare(species,alpha,L,t_pulse,solver):
    """Plot the DEM for different runs of EBTEL-2fluid with differing waiting times.

    Arguments:
    species -- which species is being heated
    alpha -- spectral power-law index (>0 here)
    t_pulse -- duration of heating pulse (s)
    solver -- solver option being used

    """
    
    #Set root directory for reading
    root_dir = '/data/datadrive2/EBTEL-2fluid_runs/' + species + '_heating_runs/'
    alpha_dir = 'alpha' + str(alpha) + '/'
    data_dir = root_dir + alpha_dir + 'data/'

    #Create the array of wait times
    wait_times = np.arange(250,5250,250)

    #Set up the figure
    fig1 = plt.figure(figsize=(10,10))
    fig2 = plt.figure(figsize=(10,7))
    fig3,ax3 = plt.subplots(3,1,figsize=(12,10))
    ax1 = fig1.gca()
    ax2 = fig2.gca()
    fs = 18

    #Set linestyle options
    line_styles = ('-','--','-.',':')
    #Set artificial spacing between lines
    delta = 0.3

    #Start the loop to read in the values
    for i in range(len(wait_times)):
        #Make the dir name
        temp_file = data_dir + 'ebtel2fl_L' + str(L) + '_tn' + str(wait_times[i]) + '_tpulse' + str(t_pulse) + '_'+ solver + '_dem.txt'
        #Load the text file
        temp = np.loadtxt(temp_file)
        #Get the logTdem and dem_cor values
        tdem = temp[:,0]
        dem_cor = temp[:,2] + i*delta
        #Find the max value
        ind_max = np.argmax(dem_cor)
        #Find the temperature at which the max occurs
        temp_max = tdem[ind_max]
        #Calculate the hot shoulder value
        hs_int=dem_shoulder_compare_integrate(temp[:,0],temp[:,2],2.0)
        hs_fit=dem_shoulder_compare_fit(temp[:,0],temp[:,2],2.0)
        #Plot the DEM values
        ax1.plot(tdem,dem_cor,linestyle=line_styles[i%4],color='blue')
        #Plot the Tmax values
        ax2.plot(wait_times[i],temp_max,'ko')
        #Plot the different shoulder strength measurements
        ax3[0].plot(wait_times[i],hs_int,'ko')
        ax3[1].plot(wait_times[i],abs(hs_fit['a_hot']),'ro')
        ax3[1].plot(wait_times[i],abs(hs_fit['a_cool']),'bo')
        ax3[2].plot(wait_times[i],abs(hs_fit['a_cool']/hs_fit['a_hot']),'ko')

    #Set some figure properties for the DEM plots
    ax1.set_title(r'EBTEL Two-fluid DEM, $T_N=250-5000$ s',fontsize=fs)
    ax1.set_xlabel(r'$\log(T_{DEM})$ (K)',fontsize=fs)
    ax1.set_ylabel(r'$\log($DEM$)$ (cm$^{-5}$ K$^{-1}$)',fontsize=fs)
    ax1.text(4.6,27.0,r'$\alpha$ = '+str(alpha),fontsize=fs)
    ax1.set_xlim([4.5,7.5])
    ax1.set_ylim([22,28.5])
    #Set some properties for the Tmax plots
    ax2.set_title(r'EBTEL Two-fluid $T(\max(DEM_C))$, $T_N=250-5000$ s',fontsize=fs)
    ax2.set_xlabel(r'$T_N$',fontsize=fs)
    ax2.set_ylabel(r'$\log(T_{max})$',fontsize=fs)
    ax2.text(500,6.8,r'$\alpha$ = '+str(alpha),fontsize=fs)
    ax2.set_ylim([5.5,7.0])
    ax2.set_xlim([wait_times[0]-250,wait_times[-1]+250])
    #Set some properties for the hot shoulder strength comparison plots
    ax3[0].set_title(r'EBTEL Two-fluid Hot Shoulder Strength Comparison',fontsize=fs)
    ax3[0].set_ylabel(r'Integration',fontsize=fs)
    ax3[0].plot([wait_times[0]-250,wait_times[-1]+250],[0.5,0.5],'--k')
    ax3[0].set_ylim([0,1])
    ax3[0].set_xlim([wait_times[0]-250,wait_times[-1]+250])
    ax3[1].set_ylabel(r'$a_{hot,cool}$',fontsize=fs)
    ax3[1].set_ylim([0,12])
    ax3[1].set_xlim([wait_times[0]-250,wait_times[-1]+250])
    ax3[2].set_ylabel(r'$a_{cool}/a_{hot}$',fontsize=fs)
    ax3[2].plot([wait_times[0]-250,wait_times[-1]+250],[1,1],'--k')
    ax3[2].set_ylim([0,5])
    ax3[2].set_xlim([wait_times[0]-250,wait_times[-1]+250])
    ax3[2].set_xlabel(r'$T_N$',fontsize=fs)
    
    #Save the figures
    plt.figure(fig1.number)
    plt.savefig(root_dir+alpha_dir+'ebtel2fl_L'+str(L)+'_tpulse'+str(t_pulse)+'_alpha'+str(alpha)+ '_' + species + '_heating_dem.eps',format='eps',dpi=1000)
    plt.figure(fig2.number)
    plt.savefig(root_dir+alpha_dir+'ebtel2fl_L'+str(L)+'_tpulse'+str(t_pulse)+'_alpha'+str(alpha)+ '_' + species + '_heating_TmaxVTn.eps',format='eps',dpi=1000)
    plt.figure(fig3.number)
    plt.savefig(root_dir+alpha_dir+'ebtel2fl_L'+str(L)+'_tpulse'+str(t_pulse)+'_alpha'+str(alpha)+ '_' + species + '_heating_hs_compare.eps',format='eps',dpi=1000)
    
    #Close the figures to avoid runtime warning of too many figures open
    plt.close(fig1)
    plt.close(fig2)
    plt.close(fig3)


