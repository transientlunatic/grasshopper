import astropy.units as u
import astropy.constants as c
import matplotlib.pyplot as plt
import numpy as np
from astropy.cosmology import WMAP9 as cosmo
import general

class Source():
    """
    The base class for a gravitational wave source.
    """
    name = "Generic Source"
    frequencies =  np.logspace(-5, 5, 1000) * u.hertz
    M = 30 * u.solMass
    r = 300 * u.parsec
    
    def __init__(self, frequencies=None, M=None, r=None):
        if frequencies: self.frequencies = frequencies
        if r: self.r = r
        if M: self.M = M
      
    def raw_strain(self, frequencies=None):
        if not frequencies: frequencies = self.frequencies
        return ((1./self.r) * ((5*np.pi)/(24*c.c**3))**(0.5) * (c.G * self.chirp_mass())**(5./6) * (np.pi*frequencies)**(-7./6)).to(1/u.hertz)
    
    def psd(self, frequencies=None):
        """
        The one-sided power spectral density
        
        Parameters
        ----------
        frequencies : ndarray
            An array of frequencies where the PSD should be calculated.
            
        Returns : ndarray
            An array of the PSDs at the given frequencies for this source.
        """
        if not frequencies: frequencies = self.frequencies
        return 2 * (frequencies**0.5) * np.abs(self.raw_strain(frequencies))
    
    def srpsd(self, frequencies=None):
        if not frequencies: frequencies = self.frequencies
        return np.sqrt(self.psd(frequencies)) 
        
    def characteristic_strain(self, frequencies=None):
        if not frequencies: frequencies = self.frequencies
        return np.sqrt(4 * frequencies**2 * np.abs(self.raw_strain(frequencies))**2)
    
    def energy_density(frequencies=None):
        if not frequencies: frequencies = self.frequencies
        return (2*pi**2)/3 * frequencies**3 * self.psd(frequencies)
    
    def plot(self, axis):
        if axis: 
            axis.loglog(self.frequencies, self.characteristic_strain(self.frequencies), label=self.name, lw=2)
            axis.set_xlabel('Frequency [Hz]')
            #axis.set_ylabel('Root Noise Power spectral density')
            axis.legend()
            
    def snr(self, detector):
        return general.snr(self, detector)
            
class CBC(Source):
    """
    A compact binary coallescence source
    """
    name = "CBC"
    M = 30 * u.solMass
    r = 300 * u.parsec
    
    def __init__(self, frequencies=None, m1=None, m2=None, r=None):
        if frequencies: self.frequencies = frequencies
        if r: self.r = r
        if m1: self.m1 = m1
        if m2: self.m2 = m2
        self.M = self.chirp_mass()
        
    def fdot(self, frequencies=None, M=None):
        """
        Calculate the first time derivative of the CBC's frequency.
        
        Parameters
        ---------
        frequencies : ndarray
            The frequencies at which the number of cycles need to be found.
            
        M : float
            The chirp mass of the CBC.
            
        Returns
        -------
        fdot : ndarray
            The df/dt of each frequency.
        """
        if not frequencies: frequencies = 0.5*self.frequencies
        if not M: M = self.chirp_mass()
        return (((96*np.pi**(8./3)) / (5 * c.c**5)) * (c.G*M)**(5./3) * frequencies**(11./3))#.to(u.hertz**2)

    def ncycles(self, frequencies=None, M=None):
        """
        Calculate the number of cycles that the CBC spends in each frequency bin.
        
        Parameters
        ---------
        frequencies : ndarray
            The frequencies at which the number of cycles need to be found.
            
        M : float
            The chirp mass of the CBC.
            
        Returns
        -------
        ncycles : ndarray
            The number of cycles in each frequency bin.
        """
        if not frequencies: frequencies = 0.5*self.frequencies
        if not M: M = self.chirp_mass()
        return np.sqrt(frequencies**2/ self.fdot(frequencies, M))#.to(1)
    
    def characteristic_strain(self, frequencies=None):
        if not frequencies: frequencies = self.frequencies
        return np.sqrt(2*self.ncycles())*np.sqrt(4 * frequencies**2 * np.abs(self.raw_strain())**2)
    
    def chirp_mass(self):
        return ((self.m1*self.m2)**(3./5) / (self.m1 + self.m2)**(1./5)).to(u.kilogram)
    
    def fisco(self):
        return ((c.c**3) / (np.pi*c.G*(self.m1+self.m2)*6*6**0.5 )).to(u.hertz)
    
    def raw_strain(self, frequencies=None):
        if not frequencies: frequencies = self.frequencies
        h = ((1./self.r) * ((5*np.pi)/(24*c.c**3))**(0.5) * (c.G * self.M)**(5./6) * (np.pi*frequencies)**(-7./6)).to(1/u.hertz)
        h[frequencies>2*self.fisco()] = np.nan
        return h

class LALException(Exception):
    pass
    
class BHBH(CBC):
    @u.quantity_input(frequencies=u.hertz, m1=u.kilogram, m2=u.kilogram, R=u.meter)
    def __init__(self, frequencies, m1, m2, S1, S2, R, inclination=0):
        self.frequencies = frequencies
        self.m1, self.m2 = m1, m2
        self.S1, self.S2 = S1, S2
        self.R = R
        self.inclination = inclination
    
    def IMRPhenom(self):
        try:
            from lalsimulation import SimInspiralChooseFDWaveform as InFD
            from lalsimulation import IMRPhenomP
        except ImportError:
            LALException("You need to install LALSimulation to use this waveform.")
            return -1
        fmin, fmax = self.frequencies.min(), self.frequencies.max()
        m1, m2 = self.m1, self.m2
        S1, S2= self.S1, self.S2
        R = self.R
        fref = 0 # reference frequency of waveform (Hz)
        fdiff = 10*u.hertz #self.frequencies.diff()[0]#.value #(frequencies.max() - frequencies.min())/(len(frequencies))
        approx = IMRPhenomP # the waveform approximant
        ampO = 0 # pN amplitude order
        phaseO = 7
        phiref = 0
        hp, hc = InFD(phiref, fdiff.value, #frequencies.diff()[0].value, 
                        m1.to(u.kilogram).value, m2.to(u.kilogram).value, 
                        S1[0], S1[1], S1[2], S2[0], S2[1], S2[2], 
                        fmin.value, fmax.value, fref, 
                        R.to(u.meter).value, self.inclination, 0., 0., 
                        None, None, 
                        ampO, phaseO, approx)
        hrss = np.sqrt(hp.data.data.real**2 + hc.data.data.real**2)
        return hrss

    def raw_strain(self, frequencies=None):
        if not frequencies: frequencies = self.frequencies
        return self.IMRPhenom()