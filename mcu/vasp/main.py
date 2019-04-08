#!/usr/bin/python
# -*- coding: utf-8 -*-

import numpy as np
import mcu
from mcu.vasp import utils, read

class VASP:
    def __init__(self, path='./', vaspruns='vasprun', outcars=None):
        '''
            path        : the project directory
            vaspruns    : a str or a list of string as names for *.xml files
            outcars     : a str or a list of string as names for OUTCAR files
        '''
        
        # Create vasprun object(s)
        if isinstance(vaspruns, str):                   # For one vasprun.xml file    
            self.vasprun = read.vasprun(path + '/' + vaspruns + '.xml')
            self.get_info(self.vasprun)
            self.useOUTCAR = False
            if outcars != None: 
                self.outcar = read.OUTCAR(outcars)
                self.useOUTCAR = True
        elif isinstance(vaspruns, list):                # For multiple vasprun.xml file
            self.vasprun = []
            for xml in vaspruns:
                xml_file = path + '/' + xml + '.xml'
                if not utils.check_exist(xml_file):
                    print('Cannot find:', xml_file)
                    break
                self.vasprun.append(read.vasprun(xml_file))
                
            self.get_info(self.vasprun[0])      # Only get info for the first vasprun.xml
            
            if outcars != None: 
                assert isinstance(outcars, list)               
                assert len(outcars) == len(vaspruns)
                self.outcar = []
                for outcar in outcars:
                    outcar_file = path + '/' + outcar
                    if not utils.check_exist(outcar_file):
                        print('Cannot find:', outcar_file)
                        break
                    self.outcar.append(read.OUTCAR(outcar_file))  
                    self.useOUTCAR = True                    
        else:
            print('Provide a string or a list of names for *.xml file')
    
    def get_info(self, vasprun):    
        '''Extract basis information from the vasprun.xml'''
        
        electronic = vasprun.parameters['electronic']
        self.nelec = electronic.general['NELECT']    
        self.nbands = electronic.general['NBANDS']
        self.lsorbit = electronic.spin['LSORBIT']
        self.ispin = electronic.spin['ISPIN']    
        self.kpts = vasprun.kpoints['kpointlist']
        self.nkpts = self.kpts.shape[0]        
        self.natom  = vasprun.natom 
        self.atom  = vasprun.atom     
        self.atm  = vasprun.atm 
        self.atype = [atom[1] for atom in vasprun.types]
        
    def get_efermi(self):
        '''Extract E_fermi either from vasprun.xml or OUTCAR'''
        if isinstance(self.vasprun, mcu.vasp.read.vasprun):
            self.vasprun.get_dos()
            if hasattr(self.vasprun,'efermi'):
                self.efermi = self.vasprun.efermi
            else:
                if self.useOUTCAR == False:
                    print ("Fermi level need to be read from OUTCAR")
                else:
                    self.efermi = self.outcar.efermi 
        elif isinstance(self.vasprun, list):        
            self.efermi = []
            for i in range(len(self.vasprun)):
                self.vasprun[i].get_dos()
                if hasattr(self.vasprun[i],'efermi'):
                    self.efermi.append(self.vasprun[i].efermi)
                else:
                    if self.useOUTCAR == False:
                        print ("Fermi level need to be read from OUTCAR")
                    else:
                        self.efermi.append(self.outcar[i].efermi)                 
            
    def get_bandgap(self, efermi=None):
        '''Get the bandgap'''
        
        # Get the fermi level
        if efermi == None: 
            self.get_efermi()
            efermi = self.efermi
            
        if isinstance(self.vasprun,mcu.vasp.read.vasprun):              # For one vasprun.xml file
            assert isinstance(efermi,float) 
            self.vasprun.get_band()
            self.band = self.vasprun.band[:,:,:,0]
            self.co_occ = self.vasprun.band[:,:,:,1] 
            self.co_occ_ = self.co_occ > 0.5       
            electronic = self.vasprun.parameters['electronic']
            ispin = electronic.spin['ISPIN']
            self.kpts = self.vasprun.kpoints['kpointlist']
            nkpts = self.kpts.shape[0]
        elif isinstance(self.vasprun,list):                             # For multiple vasprun.xml file
            assert isinstance(efermi,list)
            for i in range(len(self.vasprun)): 
                assert isinstance(efermi[i],float)
                
            electronic = self.vasprun[0].parameters['electronic']
            nbands = electronic.general['NBANDS']
            ispin = electronic.spin['ISPIN']
            
            band_spin = [] 
            co_occ_spin1 = []
            co_occ_spin2 = []            
            for spin in range(ispin):
                bands = np.zeros([1,nbands])
                co_occ1 = np.zeros([1,nbands])    
                co_occ2 = np.zeros([1,nbands], dtype=bool)                 
                kptss = np.zeros([1,3])
                for i, vasprun in enumerate(self.vasprun):
                    vasprun.get_band()
                    band = vasprun.band[spin,:,:,0]
                    kpts = vasprun.kpoints['kpointlist']
                    weight = vasprun.kpoints['weights']
                    nonzero = np.count_nonzero(weight)
                    kpts, band = kpts[nonzero:], band[nonzero:]
                    co_occ = vasprun.band[spin,nonzero:,:,1]
                    co_occ_ = band < efermi[i] 
                    bands = np.vstack([bands,band])
                    kptss = np.vstack([kptss,kpts])
                    co_occ1 = np.vstack([co_occ1,co_occ])
                    co_occ2 = np.vstack([co_occ2,co_occ_])
                band_spin.append(bands[1:])  
                co_occ_spin1.append(co_occ1[1:])   
                co_occ_spin2.append(co_occ2[1:])  
            self.kpts, self.band = np.asarray(kptss[1:]), np.asarray(band_spin)
            nkpts = self.kpts.shape[0]
            self.co_occ, self.co_occ_ = np.asarray(co_occ_spin1), np.asarray(co_occ_spin2)
            
        bandedge = np.zeros([ispin,nkpts,2,2])
        self.bandgap = []
        for spin in range(ispin):
            print('Spin:', spin)        
            for kpt in range(nkpts):
                band_kpt = self.band[spin,kpt]
                occ = self.co_occ_[spin,kpt]               
                homo_idx = np.count_nonzero(occ) - 1
                lumo_idx = homo_idx + 1               
                bandedge[spin,kpt,0,0] = band_kpt[homo_idx]
                bandedge[spin,kpt,0,1] = self.co_occ[spin,kpt,homo_idx]
                bandedge[spin,kpt,1,0] = band_kpt[lumo_idx]
                bandedge[spin,kpt,1,1] = self.co_occ[spin,kpt,lumo_idx]
                
            vbm_idx = np.argmax(bandedge[spin,:,0,0])
            cbm_idx = np.argmin(bandedge[spin,:,1,0])
            direct = False
            if vbm_idx == cbm_idx: direct = True
            print('  E(VBM) = %7.4f with occ = %7.4f at k = [%6.4f,%6.4f,%6.4f]' % (bandedge[spin,vbm_idx,0,0], bandedge[spin,vbm_idx,0,1], 
                                                            self.kpts[vbm_idx,0],self.kpts[vbm_idx,1],self.kpts[vbm_idx,2]))
            print('  E(CBM) = %7.4f with occ = %7.4f at k = [%6.4f,%6.4f,%6.4f]' % (bandedge[spin,cbm_idx,1,0], bandedge[spin,cbm_idx,1,1], 
                                                            self.kpts[cbm_idx,0],self.kpts[cbm_idx,1],self.kpts[cbm_idx,2]))
            bandgap = bandedge[spin,cbm_idx,1,0] - bandedge[spin,vbm_idx,0,0] 
            self.bandgap.append(bandgap)  
            if direct == True: 
                print('  Direct bandgap   : %6.3f' % (bandgap))             
            else:  
                print('  Indirect bandgap : %6.3f' % (bandgap))              
                gap1 = bandedge[spin,cbm_idx,1,0] - bandedge[spin,cbm_idx,0,0]
                gap2 = bandedge[spin,vbm_idx,1,0] - bandedge[spin,vbm_idx,0,0]  
                direct_gap = gap1
                if gap1 > gap2: direct_gap = gap2
                print('  Direct bandgap   : %7.4f' % (direct_gap))                   
                
                
    def _generate_band(self, vasprun, efermi=None, spin=0, label=None):
        '''Processing/collecting the band data before the plotting function
        '''
        
        # Get the fermi level
        if efermi == None: 
            self.get_efermi()
            efermi = self.efermi        
        
        sym_kpoint_coor = None
        band = None
        path = None
        conventional = False
            
        if isinstance(vasprun,mcu.vasp.read.vasprun) and vasprun.kpoints['type'] == 1: # For conventional band structure calculation 
            if label != None:
                assert isinstance(label,str)     # label needs to be a string in the format,e.g. 'A-B-C-D'
                label = label.split('-')
            assert isinstance(efermi,float)
            conventional = True  
            vasprun.get_band()
            band = vasprun.band[spin][:,:,0]
            kpts = vasprun.kpoints['kpointlist']
            kpts, band = utils.rm_redundant_band(kpts, band) 
            
            # Find absolute kpts and shift the band
            b = vasprun.cell_final[1]          # Get the reciprocal lattice
            abs_kpts = kpts.dot(b)                  # From fractional to absolute
            temp_kpts = np.empty_like(abs_kpts)
            temp_kpts[0] = abs_kpts[0]
            temp_kpts[1:] = abs_kpts[:-1] 
            path = np.matrix(np.sqrt(((temp_kpts - abs_kpts)**2).sum(axis=1)).cumsum())
            band = band - efermi               # Efermi is set at 0 eV
            
            highsym_kpt = vasprun.kpoints['points']
            nkpts = highsym_kpt.shape[0]
            sym_kpoint_coor = [0.0]
            for kpt in range(nkpts-2):
                idx = ((path.shape[1] + nkpts - 2)//(nkpts-1) - 1) * (kpt+1)
                coor = path[0,idx]         
                sym_kpoint_coor.append(coor)
            sym_kpoint_coor.append(1.0*path.max())   
            sym_kpoint_coor = np.asarray(sym_kpoint_coor)
                     
        else:
            if isinstance(vasprun,mcu.vasp.read.vasprun):                       # For one vasprun.xml file
                assert isinstance(efermi,float)
                vasprun = vasprun
                vasprun.get_band()
                band = vasprun.band[spin][:,:,0]
                kpts = vasprun.kpoints['kpointlist']
                if vasprun.kpoints['type'] == 0:
                    weight = vasprun.kpoints['weights']
                    nonzero = np.count_nonzero(weight)
                    kpts, band = kpts[nonzero:], band[nonzero:]
                band = band - efermi
            elif isinstance(vasprun,list):                                      # For multiple vasprun.xml file
                assert isinstance(efermi,list)
                for i in range(len(self.vasprun)): 
                    assert isinstance(efermi[i],float)
                
                electronic = vasprun[0].parameters['electronic']
                nbands = electronic.general['NBANDS']
                bands = np.zeros([1,nbands])
                kptss = np.zeros([1,3])
                for i, run in enumerate(vasprun):
                    run.get_band()
                    band = run.band[spin][:,:,0]
                    kpts = run.kpoints['kpointlist']
                    weight = run.kpoints['weights']
                    nonzero = np.count_nonzero(weight)
                    kpts, band = kpts[nonzero:], band[nonzero:]
                    band = band - efermi[i]
                    bands = np.vstack([bands,band])
                    kptss = np.vstack([kptss,kpts])
                    
                kpts, band = kptss[1:], bands[1:]
                vasprun = vasprun[0]
                
            # Find absolute kpts
            b = vasprun.cell_final[1]          # Get the reciprocal lattice
            abs_kpts = kpts.dot(b)                  # From fractional to absolute
            temp_kpts = np.empty_like(abs_kpts)
            temp_kpts[0] = abs_kpts[0]
            temp_kpts[1:] = abs_kpts[:-1] 
            path = np.matrix(np.sqrt(((temp_kpts - abs_kpts)**2).sum(axis=1)).cumsum())

            # Find absolute coordinates for high symmetric kpoints  
            if label != None:
                assert isinstance(label,list)           # label needs to be a list of labels and corresponding coordinates
                temp = []
                coor_kpts = [] 
                for kpt in label:
                    temp.append(kpt[0])
                    coor_kpts.append(kpt[1:])
                label = temp       
                coor_kpts = np.asarray(coor_kpts)
                abs_kpts = coor_kpts.dot(b)   
                temp_kpts = np.empty_like(abs_kpts)
                temp_kpts[0] = abs_kpts[0]
                temp_kpts[1:] = abs_kpts[:-1] 
                sym_kpoint_coor = np.sqrt(((temp_kpts - abs_kpts)**2).sum(axis=1)).cumsum() 
        
        return band, path, sym_kpoint_coor, label, conventional
                
    def plot_band(self, efermi=None, spin=0, label=None, save=False,
                    figsize=(5,8), ylim=[-6,6], fontsize=18, dpi=600, format='png'):
        '''Plot band structure
           
            Attribute:
                efermi          : a Fermi level or a list of Fermi levels
                spin            : 0  for spin unpolarized and LSORBIT = .TRUE.
                                  0 or 1 for spin polarized
                label           : label for high symmetric points, e.g. 'G-X-L-W-G'
                                  if hybridXC=True, the lavel should be a list of labels plus their coordinates
        '''
        
        # matplotlib is required
        import matplotlib
        import matplotlib.pyplot as plt
            
        band, path, sym_kpoint_coor, label, conventional = self._generate_band(self.vasprun, efermi, spin, label)  

        ##----------------------------------------------------------
        ##Plotting:        
        ##----------------------------------------------------------
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111)
        yrange = (-50,50)
        
        # Plot the high symmetric kpoint grid
        if conventional == True or label != None:
            for kpt in range(sym_kpoint_coor.shape[0]):
                ax.plot([sym_kpoint_coor[kpt]]*2,yrange,color="#808080",linewidth=1.0)

        if label != None:
            nkpts = len(label)
            assert nkpts == sym_kpoint_coor.shape[0]        # The numbers of label should be match with the # of coordiantes provided
            for kpt in range(nkpts):   
                point = label[kpt]
                if point == 'G': point = r'$\Gamma$'
                ax.text(sym_kpoint_coor[kpt]/path.max()+0.02, -0.05, point, verticalalignment='bottom', horizontalalignment='right',transform=ax.transAxes,
                        color='black', fontsize=fontsize)     
            
        # Plot bands            
        ax.plot([0,path.max()],[0,0],color="#808080",linewidth=1.0, dashes=[6,3])
        for ith in range(band.shape[1]):
            ax.plot(path.T,band[:,ith],color="#007acc",linewidth=1.0)    
             
        # Graph adjustments             
        ax.tick_params(labelsize=fontsize)
        plt.xlabel('k', size=fontsize+4)
        ax.xaxis.set_label_coords(0.5, -0.08) 
        plt.ylabel('Energy (eV)', size=fontsize+4)        
        plt.ylim(ylim)
        plt.xlim([0,path.max()])
        plt.xticks([])
        plt.tight_layout()
        if save == True: 
            fig.savefig('Band.'+format,dpi=dpi,format=format)      
        else:
            plt.show()            
            
        
    def _generate_pband(self, vasprun, spin=0, style=1, lm='spd', lm_label=None):
        '''Processing/collecting the projected band data before the plotting function
            proj_wf = [spin,kpt,band,atom,lm] , read mcu.vasp.read.vasprun.get_projected for more details info
            
            style = 0   : all atoms are considered, user proves the lm
                         lm = 's', 'py', 'pz', 'px', 'dxy', 'dyz','dz2','dxz','dx2-y2' or a list of them lm ['s', ['px','pz']]
                         'p', 'd', 'sp', 'pd', 'sd', 'spd': shortcuts 
                         each color is used for each lm
                             
            style = 1   : gradient map to show the character transition
                         lm = 'sp', 'pd', 'sd', or a list ['s',['px','dx2-y2']]
            
            style = 2   : considering only a list of orbitals
                         e.g. lm = 'Ni:s', ['Ni:s','C:s,px,pz']

            band        : [first_band, final_band]
                          by default, it is roughly 6 bands around fermi level
                          
        '''      
       
        
        # Collecting/combining the projected wfn from vasprun.xml
        if isinstance(vasprun,mcu.vasp.read.vasprun):                       # For one vasprun.xml file
            vasprun.get_projected()
            proj_wf = vasprun.proj_wf[spin] 
            lm_list = vasprun.lm           
            proj_wf = utils.rm_redundant_band(self.kpts, proj_wf)[1]          # remove redundant 
        
        elif isinstance(vasprun,list):                                      # For multiple vasprun.xml file
            nlm    = len(vasprun[0].get_lm())
            lm_list = vasprun[0].lm
            proj_wfs = np.zeros([1,self.nbands,self.natom,nlm])
            
            for i, run in enumerate(vasprun):
                run.get_projected()
                proj_wf = run.proj_wf[spin]
                kpts = run.kpoints['kpointlist']
                weight = run.kpoints['weights']
                nonzero = np.count_nonzero(weight)
                proj_wf = proj_wf[nonzero:]
                proj_wfs = np.concatenate((proj_wfs,proj_wf))   
            proj_wf = proj_wfs[1:]
         

        if style == 1:
            lm_shortcut = ['p','d','sp','ps','pd','dp','sd','ds','spd','sdp','psd','pds','dsp','dps']
            # Check if the lm value is appropriate
            if isinstance(lm,str):
                if lm not in lm_list and lm not in lm_shortcut:
                    raise Exception("WARNING:", lm, "is not recognizable. lm must be", lm_list, lm_shortcut)
                else:
                    if lm == 'p': 
                        lm = [['px','py','pz']]
                    elif lm == 'd': 
                        lm = [['dxy', 'dyz','dz2','dxz','dx2-y2']]
                    elif lm == 'sp': 
                        lm = ['s',['px','py','pz']]
                    elif lm == 'ps': 
                        lm = [['px','py','pz'],'s']
                    elif lm == 'sd': 
                        lm = ['s',['dxy', 'dyz','dz2','dxz','dx2-y2']]
                    elif lm == 'ds': 
                        lm = [['dxy', 'dyz','dz2','dxz','dx2-y2'],'s']
                    elif lm == 'pd': 
                        lm = [['px','py','pz'],['dxy', 'dyz','dz2','dxz','dx2-y2']]
                    elif lm == 'dp': 
                        lm = [['dxy', 'dyz','dz2','dxz','dx2-y2'],['px','py','pz']]
                    elif lm == 'spd':                         
                        lm = ['s',['px','py','pz'],['dxy', 'dyz','dz2','dxz','dx2-y2']]  
                    elif lm == 'sdp':                         
                        lm = ['s',['dxy', 'dyz','dz2','dxz','dx2-y2'],['px','py','pz']] 
                    elif lm == 'psd':                         
                        lm = [['px','py','pz'],'s',['dxy', 'dyz','dz2','dxz','dx2-y2']]   
                    elif lm == 'pds':                         
                        lm = [['px','py','pz'],['dxy', 'dyz','dz2','dxz','dx2-y2'],'s']  
                    elif lm == 'dsp':                         
                        lm = [['dxy', 'dyz','dz2','dxz','dx2-y2'],'s',['px','py','pz']] 
                    elif lm == 'dps':                         
                        lm = [['dxy', 'dyz','dz2','dxz','dx2-y2'],['px','py','pz'],'s']                          
                    else:
                        lm = [lm]
            elif isinstance(lm,list):
                for each_lm in lm:
                    if isinstance(each_lm,str):
                        if each_lm not in lm_list:
                            raise Exception("WARNING:", lm, "is not recognizable. lm must be one of these", lm_list)
                    else:
                        for orb in each_lm:
                            if orb  not in lm_list:
                                raise Exception("WARNING:", orb , "is not recognizable. lm must be one of these", lm_list)                        
            else:
                raise Exception("lm is not recognizable")
                
            # Compute pband
            proj_wf = proj_wf.sum(axis=2)       # Sum over the atoms --> [kpt,band,lm]
            total = proj_wf.sum(axis=2)         # Sum over the lm  --> [kpt,band]
            pband = [] 
            for each_lm in lm:
                if isinstance(each_lm,str):  
                    idx_lm = lm_list.index(each_lm)
                    proj_val = proj_wf[:,:,lm_list.index(each_lm)]/total
                else:
                    proj_val = 0
                    for orb in each_lm:
                        idx_lm = lm_list.index(orb)
                        proj_val += proj_wf[:,:,idx_lm]/total
                pband.append(proj_val)
            pband = np.asarray(pband)
          
        elif style == 2:
            if isinstance(lm,str):
                atom, lm_ = lm.split(':')
                lm_  = lm_.split(',') 
                temp = []
                for i in range(len(lm_)):               
                    if lm_[i] == 'p': 
                        for m in ['px','py','pz']: temp.append(m)
                    elif lm_[i] == 'd': 
                        for m in ['dxy', 'dyz','dz2','dxz','dx2-y2']: temp.append(m)
                    else:
                        temp.append(lm_[i])
                lms = [temp]
                atoms = [atom]
                
            elif isinstance(lm,list):
                atoms = []
                lms = []   
                atom_list = self.vasprun.atom
                for orb in lm:
                    atom, lm_ = orb.split(':')
                    lm_  = lm_.split(',') 
                    temp = []
                    for i in range(len(lm_)):               
                        if lm_[i] == 'p': 
                            for m in ['px','py','pz']: temp.append(m)
                        elif lm_[i] == 'd': 
                            for m in ['dxy', 'dyz','dz2','dxz','dx2-y2']: temp.append(m)
                        else:
                            temp.append(lm_[i])
                    atoms.append(atom)
                    lms.append(temp)
                
            # Compute pband
            pband = [] 
            total = proj_wf.sum(axis=(2,3))       # Sum over the atoms --> [kpt,band,lm]
            for i in range(len(atoms)):
                idx_atom = [idx for idx in range(len(self.atom)) if atoms[i] == self.atom[idx]]
                idx_lm = [lm_list.index(lm) for lm in lms[i]] 
                proj_val_atom = 0
                proj_val = 0                
                for idx in idx_atom: proj_val_atom += proj_wf[:,:,idx,:]
                for idx in idx_lm: proj_val += proj_val_atom[:,:,idx]
                pband.append(proj_val/total)
            pband = np.asarray(pband)
            
        elif style == 3: 
            lm_shortcut = ['sp', 'sd', 'pd']
            if isinstance(lm,str):
                if lm not in lm_shortcut:
                    raise Exception("WARNING:", lm, "is not recognizable. lm must be", lm_shortcut)
                else:
                    if lm == 'sp': 
                        lm = ['s',['px','py','pz']]
                    elif lm == 'sd': 
                        lm = ['s',['dxy', 'dyz','dz2','dxz','dx2-y2']]
                    elif lm == 'pd': 
                        lm = [['px','py','pz'],['dxy', 'dyz','dz2','dxz','dx2-y2']]
                    else:
                        raise Exception("WARNING:", lm, "is not recognizable. lm must be one of these", lm_shortcut, "or a list")
            elif isinstance(lm,list):
                assert len(lm) == 2          # Only two orbital 
                for each_lm in lm:
                    if isinstance(each_lm,str):
                        if each_lm not in lm_list:
                            raise Exception("WARNING:", lm, "is not recognizable. lm must be one of these", lm_list)
                    else:
                        for orb in each_lm:
                            if orb  not in lm_list:
                                raise Exception("WARNING:", orb , "is not recognizable. lm must be one of these", lm_list) 
            else:
                raise Exception("lm is not recognizable")
                
            # Compute pband
            proj_wf = proj_wf.sum(axis=2)       # Sum over the atoms --> [kpt,band,lm]
            pband = [] 
            for each_lm in lm:                  # only two lm
                if isinstance(each_lm,str):  
                    idx_lm = lm_list.index(each_lm)
                    proj_val = proj_wf[:,:,idx_lm]
                else:
                    proj_val = 0
                    for orb in each_lm:
                        idx_lm = lm_list.index(orb)
                        proj_val += proj_wf[:,:,idx_lm]
                pband.append(proj_val)
            pband = np.asarray(pband)
            pband = pband[0]/(pband.sum(axis=0))
        else:
            raise Exception('mcu currently supports only style: 0,1,2')
        
        return pband
                
                    
    def plot_pband(self, efermi=None, spin=0, label=None, style=1, lm='spd', band_idx=None, color=None,
                    scale=1.0, alpha=0.5, cmap='bwr', edgecolor='none', facecolor=None, 
                    legend=None, loc="upper right", legend_size=22, 
                    save=False, figsize=(6,6), ylim=[-6,6], fontsize=18, dpi=600, format='png'):
        '''Plot projected band structure
           
            Attribute:
                efermi      : a Fermi level or a list of Fermi levels, it is automatically extracted frim vasprun.xml or OUTCAR, consider to remove
                spin        : 0  for spin unpolarized and LSORBIT = .TRUE.
                                  0 or 1 for spin polarized
                label       : label for high symmetric points, e.g. 'G-X-L-W-G',
                                  if hybridXC=True, the lavel should be a list of labels plus their coordinates
                                  
                ########################PLOTTING STYLE###################################
                style = 1   : all atoms are considered
                             lm = 's', 'py', 'pz', 'px', 'dxy', 'dyz','dz2','dxz','x2-y2' or a list of them
                                 'sp', 'pd', 'sd', 'spd'  => shortcut
                                 each color is used for each lm
                                 the marker's radius is proportional to the % of lm 
                style = 2   : considering only a list of orbitals
                             e.g. orb = ['Ni_s','C_pz']
                style = 3   : gradient map to show the character transition
                             lm = 'sp', 'pd', 'sd'
                #########################################################################
                             
                band_idx    : the first value indicates the number of valence bands from the VBM
                              the second value indicates the number of conduction bands from the CBM
                color       : a list of strings indicating the color, following matplotlib
                scale       : the size of the marker in style 1 and 2
                alpha       : the transparency level of curves
                cmap        : color map in the style 3, following the matplotlib
                edgecolor   : the marker's border color in the style 3, default: 'none', any color code should work
                facecolor   : the filling color of style 1 and 2
                              None              : taking from the color arg
                              'none'            : unfilling circle
                              [False,True,...]  : True for filling markers and False for empty ones
                legend      : a list of labels for different group of orbitals (same color) for the style 1 and 2            
        '''
                    
        # matplotlib is required
        import matplotlib
        import matplotlib.pyplot as plt
        
        if style == 2 and lm == 'spd' : lm = [atom+':s,p,d' for atom in self.atype]       
        if style == 3 and lm == 'spd' : lm = 'sp'
       
        # Check if the band values are reasonable otherwise generate it
        if band_idx == None:
            idx_vbm = self.nelec
            if self.lsorbit == False: idx_vbm = idx_vbm//2               # Estimation for insulator, generally wrong for metal
            first_band = int(idx_vbm - 5)
            last_band = int(idx_vbm + 4)
            if first_band < 0: first_band = 0
            if last_band > self.nbands - 1: last_band = self.nbands - 1
            band_idx = [first_band, last_band]
        else:
            assert band_idx[0] <= band_idx[1]                    # from band[0] to band[1]
            if band_idx[0] < 1: band_idx[0] = 1     # index used in OUTCAR, will be shifted to start at zero
            if band_idx[1] > self.nbands: band_idx[1] = self.nbands              # Cannot larger than the number of bands
            band_idx[0] = band_idx[0] -1
            band_idx[1] = band_idx[1] -1     
        
        band, path, sym_kpoint_coor, label, conventional = self._generate_band(self.vasprun, efermi, spin, label)  
        pband = self._generate_pband(self.vasprun, spin, style, lm)
        
        ##----------------------------------------------------------
        ##Plotting:        
        ##----------------------------------------------------------
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111)
        yrange = (-50,50)
        
        # Customization:
        border = 1.08
        
        # Plot the high symmetric kpoint grid
        if conventional == True or label != None:
            for kpt in range(sym_kpoint_coor.shape[0]):
                ax.plot([sym_kpoint_coor[kpt]]*2,yrange,color="#808080",linewidth=1.0)

        if label != None:
            nkpts = len(label)
            assert nkpts == sym_kpoint_coor.shape[0]        # The numbers of label should be match with the # of coordiantes provided
            for kpt in range(nkpts):   
                point = label[kpt]
                if point == 'G': point = r'$\Gamma$'
                ax.text(sym_kpoint_coor[kpt]/path.max()+0.02, -0.065, point, verticalalignment='bottom', horizontalalignment='right',transform=ax.transAxes,
                        color='black', fontsize=fontsize)     
            
        # Plot bands            
        ax.plot([0, path.max()], [0,0], color="#808080", linewidth=1.0, dashes=[6,3])
        for ith in range(band.shape[1]):
            ax.plot(path.T, band[:,ith], color="#007acc",linewidth=1.0)    
             
        # Plot pbands 
        color_list = ['r','g','b','y','m','c']
        path = np.array(path).flatten() 
        if style == 1 or style == 2:
            pband = 200 * scale * np.power(pband,2)     # The radius of the marker ~ the percent 
            
            # Color
            if color == None: color = color_list
            if facecolor == None: 
                fcolors = color
            elif isinstance(facecolor,list):
                assert len(facecolor) == len(pband)
                fcolors = []
                for i in range(len(facecolor)):
                    assert facecolor[i] == True or facecolor[i] == False
                    if facecolor[i] == True: fcolors.append(color[i]) 
                    if facecolor[i] == False: fcolors.append('none') 
            elif facecolor == 'none':
                fcolors = ['none']*len(pband)

            # legend    
            if legend != None:
                legends = []   
                assert isinstance(legend,list)
                assert len(legend) == len(pband)
                
            # Actual plotting
            for lm in range(len(pband)):
                for ith in range(band_idx[0],band_idx[1]):
                    ax.scatter(path, band[:,ith], s=pband[lm][:,ith], facecolors=fcolors[lm], edgecolors=color[lm], alpha=alpha)
                ith = band_idx[1]
                if legend == None:
                    ax.scatter(path, band[:,ith], s=pband[lm][:,ith], facecolors=fcolors[lm], edgecolors=color[lm], alpha=alpha)
                else:
                    ax.scatter(path, band[:,ith], s=pband[lm][:,ith], facecolors=fcolors[lm], edgecolors=color[lm], alpha=alpha, label=legend[lm])                    
                
            if legend != None: 
                lgnd = ax.legend(loc=loc, numpoints=1, fontsize=fontsize)
                for i in range(len(pband)): lgnd.legendHandles[i]._sizes = [legend_size]
                
        elif style == 3:
            path = np.array(path).flatten()
            for ith in range(band_idx[0],band_idx[1]+1):
                plt.scatter(path, band[:,ith], c=pband[:,ith], vmin=0.0, vmax=1., cmap=cmap, edgecolor=edgecolor) 
            cbar = plt.colorbar(ticks=[])
            cbar.outline.set_linewidth(border)
        
        # Graph adjustments             
        ax.tick_params(labelsize=fontsize, width=border)
        ax.spines['top'].set_linewidth(border)
        ax.spines['right'].set_linewidth(border)
        ax.spines['bottom'].set_linewidth(border)
        ax.spines['left'].set_linewidth(border)
        plt.xlabel('k', size=fontsize+4)
        ax.xaxis.set_label_coords(0.5, -0.08) 
        plt.ylabel('Energy (eV)', size=fontsize+4)        
        plt.ylim(ylim)
        plt.xlim([0,path.max()])
        plt.xticks([])
        plt.tight_layout()
        if save == True: 
            fig.savefig('Band.'+format, dpi=dpi, format=format)      
        else:
            plt.show() 
            
        
    def plot_dos(self):
        pass       
      
        
        

