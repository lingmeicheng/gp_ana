# Script to read GP35 data produced by the RUST DAQ software
# and in particular build the coinctable.txt file
# to be used for the TREND recons software

# OMH January 2019



import os
import sys
sys.path.append("../")
import pyef

import numpy as np
import pylab as pl
import yaml

pl.ion()
c0 = 299792458
DISPLAY = 1
datafolder = "/home/martineau/GRAND/GRANDproto35/data/ulastai"
#datafolder = "/mnt/disk"
#IDsin = []
utcSLC = []    
maxCoarse = []
def twos_comp(val, bits):
    """compute the 2's compliment of int value val"""
    if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)        # compute negative value
    return val   


def loadMaxCoarse(runid): 
  global IDsin
  allIDs = []
  allUTC = []
  allMaxCoarse = []
  slcfile = datafolder+"/S"+runid+".yaml"
  if os.path.isfile(slcfile) is False:
     print('File ',slcfile,'does not exist. Aborting.')
     IDsin = []
     return
  
  # Now read SLC file ad dump infos in arrays
  print('Scanning SLC file',slcfile)
  print("Loading SLC data...")
  dataf=yaml.load_all(open(slcfile))
  print("Done.")
  for d in dataf:
    if d['msg_type']=='SLC':
      allIDs.append(d['source_ip'][3]-100)
      allUTC.append(d['received_timestamp'][0])
      allMaxCoarse.append(d['max_coarse'])
      
  allIDs = np.array(allIDs)
  allUTC = np.array(allUTC)
  allMaxCoarse = np.array(allMaxCoarse)
  IDsin = np.unique(allIDs)
  print("MaxCoarse info retrieved for following units:",IDsin)
  
  # Now order info according to Unit ID
  for uid in IDsin:
    ind = np.nonzero(allIDs==uid)
    utcSLC.append(allUTC[ind])
    maxCoarse.append(allMaxCoarse[ind])
    
    
def getMaxCoarse(uid,utcsec):
  #try:
  #  if len(IDsin) == 0:  # SLC data was not yet loaded
  #    print("Ooops... No MaxCoarse info yet! Fetching it from SLC data.")
  #    loadMaxCoarse(sys.argv[1])     
  #  else:
  #    print("MaxCoarse info available for following units",IDsin)
     
  #except:
  #  print("Ooops... No MaxCoarse info yet! Fetching it from SLC data.")
  #  loadMaxCoarse(sys.argv[1])      
  
  
  # Now retrieve proper maxCoarse info
  i = np.nonzero(IDsin == uid)[0]  
  if len(i)>0:  # Unit found in SLC data
    i = i[0]
    indt = np.argmin(np.abs(utcSLC[i]-utcsec))
    #print(utcsec,utcSLC[i][indt],maxCoarse[i][indt])
  else:  # Unit not found in LSC data
    return 0
    
  return maxCoarse[i][indt]

  
def build_distmat():
  # Build matrix of d(ant1,ant2)
  antfile = "ants.txt"
  pos = np.loadtxt(antfile,delimiter=',')
  a = np.array([('a', 2), ('c', 1)], dtype=[('x', 'S1'), ('y', int)])
  uid=pos[:,0]
  nants = len(uid)
  x=pos[:,2]
  y=pos[:,1]
  z=pos[:,3]
  #p = [x, y, z]  # Why cannot numpy build matrixes with this syntax?????????? Makes me crazy
  p = np.vstack((x,y,z))
  d = np.ndarray(shape=(nants,nants))  
  for i in range(nants):
    for j in range(nants):
      #print(np.linalg.norm(p[:,j]-p[:,i]))
      d[i,j] = np.linalg.norm(p[:,j]-p[:,i])
      d[j,i] = d[i,j]
  
  return uid,d


def build_coincs(trigtable,uid,d):
# Search for coincs
  print("Now searching for coincidences...")
  ntrigs = np.shape(trigtable)[0]
  tmax = np.max(d)/c0*1e9*1.5  # Factor 1.5 to give some flexibility # TBD: adjust for each pair of antennas
  #tmax = 2000 # Impose 1mus for now 
  uid = trigtable[:,0]  # Vector of unit UDs
  secs = trigtable[:,1]  # Vector of seconds info
  secscor = secs-min(secs)  #  Use f1st second as reference. Otherwise "times" field is too long and subsequent operations fail...
  nsecs = trigtable[:,2] # Vector of nanoseconds info
  times = secscor*1e9+nsecs # Build complete time info. Units = ns. 
  
  #
  i = 0
  coinc_nb = 0
  delays = []
  uid_delays = []
  filename = 'R{0}_coinctable.txt'.format(sys.argv[1])  # File where coincs should be written, latter used for source reconstruction
  while i<ntrigs:   
  # Loop on all triggers in table
    trig_ref = times[i]
    id_ref = uid[i]
    tsearch = times[i:-1]-trig_ref
    tsearch = tsearch[np.argwhere(tsearch<tmax)].T[0]  #  Search in causal timewindow. Transpose needed to get a line vector and avoid []
    idsearch = uid[i:i+len(tsearch)]
    #print(i,"*** Reference unit:",i,id_ref,uid[i],secs[i],nsecs[i],trig_ref,times[i],", now looking for coincs within",tmax,"ns")
    #print(idsearch,tsearch)
    _, coinc_ind = np.unique(idsearch, return_index = True) # Remove multiple triggers from a same antenna
    if len(coinc_ind)>3:  # Require 4 antennas at least to perform recons
      # there are events in the causal timewindow
      coinc_nb = coinc_nb+1  # INcrement coinc counter
      #print(i,"*** Reference unit:",id_ref,times[i],", now looking for coincs within",tmax,"ns")
      #print(np.argwhere(tsearchini<tmax),tsearchini[0:10])
      #print("Units in causal timewindow:",i,i+len(tsearch),idsearch,tsearch,secs[i:i+len(tsearch)],nsecs[i:i+len(tsearch)])
      #print("From different units:",idsearch[others],tsearch[others],others)
      mult = len(coinc_ind)
      print(coinc_nb,": possible coinc at (",int(secs[i]),"s;",nsecs[i],"ns) between",mult,"units:",idsearch[coinc_ind],tsearch[coinc_ind])

      coinc_ids = idsearch[coinc_ind]
      coinc_ids = np.array([coinc_ids])  # Anybody able to explain why coinc_id is not a numpy.array???
      coinc_times = tsearch[coinc_ind]
      coinc_times = np.array([coinc_times])
      
      # Write to file
      # Format: Unix sec; Unit ID, Evt Nb, Coinc Nb, Trig time (ns), [0]x7 
      evts = np.array([range(i,i+mult)],dtype = int).T
      one = np.ones((mult,1),dtype=int)
      this_coinc = np.hstack((secs[i]*one,coinc_ids.T,evts,coinc_nb*one,coinc_times.T))
      #print(this_coinc)
      if coinc_nb == 1:
        all_coincs = this_coinc
      else:
        all_coincs = np.concatenate((all_coincs,this_coinc))

      # Now load delay info (only for histos)
      delays = np.concatenate((delays,coinc_times[coinc_ids!=id_ref]))
      uid_delays = np.concatenate((uid_delays,coinc_ids[coinc_ids!=id_ref]))
      i = i+len(coinc_ind)
      
    else:
      i = i+1
  
  np.savetxt(filename,all_coincs,fmt='%d')  # Write to file
          
  if DISPLAY:
    uid_delays = np.array(uid_delays)
    uid = np.unique(uid_delays)
    #delays = np.array(delays)
    pl.figure(8)
    for i in uid:
      pl.hist(delays[uid_delays==i],200,label='ID{0}'.format(int(i)))
    pl.xlim([0,tmax])
    pl.legend(loc='best')
    pl.xlabel('Trigger delay (ns)')
    pl.show()
                    
		  
		    
def get_time(nrun=None,pyf=None):
# Retrieves time info from datafile
  print("Now building trigger time table from data...")
  if pyf == None:
    print("No pyef object, loading it from run number.")
    if nrun == None:
      print("get_time error! Pass run number or pyef object as argument")
      return
    pyf = load_data(nrun)
  
  if nrun == None:
    nrun = sys.argv[1]
    
  nevts = len(pyf.event_list)
  #print(nevts,"events in file",datafile)
  # TBD: access file header

  # Loop on all events
  secs = []
  nsecs = []
  ttimes = []
  IDs = []
  i = 0
  for evt in f.event_list:
    #print("\n\n!!!New event!!!")
    # Loop on all units in the event (at present should be only one)
    for ls in evt.local_station_list:
    # Loop on all units involved in event (should be one only at this stage)
      #print("Local unit info")
      #ls.display()
      uid = int(ls.header.ls_id-356) # 16 lowest bits of IP adress --256 to go down to 8 lowest digits of IP adress & -100 to go down to antenna ID
      IDs.append(uid) 
      #nsec = ls.header.gps_nanoseconds  # GPS info for that specific unit
    
    h = evt.header
    sec = h.event_sec
    # Correct for possible SSS offset error - To Be Fixed
    #if sys.argv[1] == "222": # Offset for 26000 1rst events. Then jump sets it correctly 
    #  if uid == 3:
    #	   sec = sec+1
    #  if uid == 5:
    #	   sec = sec+1  	 
    #  if uid == 18:
    #      sec = sec+1  
    #if sys.argv[1] == "230":  # Offset for 22000 first events. Then jump sets it correctly 
    #  if uid == 9:
    #    sec = sec
    nsec = h.event_nsec

    # Now correct time from maxCoarse value
    maxcoarse = getMaxCoarse(uid,sec)
    cor=125e6/(getMaxCoarse(uid,sec)+1)
    if abs(cor-1)>0.01: # Abnormal correction value
      cor = 1
    nsec = nsec*cor
    nsecs.append(nsec)
    secs.append(sec)

    #print("Event",i,", ID=",uid,",Time=",sec,nsec)
    #print("Event info")
    #evt.display()
    #print("Header info")
    #h.display()
    i = i+1
    
  secs = np.array(secs)
  nsecs = np.array(nsecs)
  # Build total time info. Warning: set 1st event as reference otherwise value too large and argsort fails!!!
  if min(secs)<1:
    print("Error!!! Minimal second info =",min(secs),". Abort.")
    return
  # Build time info  
  ttimes = (secs-min(secs))*1e9+nsecs  # Set 1st event as reference
  ttimes = np.array(ttimes,dtype=int)
  ttimes = (ttimes-min(ttimes))/1e9
  # Order in time
  IDs = np.array(IDs)
  units = np.unique(IDs)
  ind = np.argsort(ttimes)
  IDs_ordered = IDs[ind]
  secs_ordered = secs[ind]
  nsecs_ordered = nsecs[ind]
  res = np.vstack((IDs_ordered,secs_ordered,nsecs_ordered))
  res = res.T
  
  # Check for errors
  # TBD: add  flag for events with time info = 0
  
  # Check for time offsets
  #tdif = np.diff(secs)
  #aid = np.argwhere(tdif<0)
  #for i in aid:
  #   print("***Warning! Possible error on SSS value for board",IDs[i+1],":\nevent",i," on board",IDs[i],": SSS =",secs[i],"\nevent",i+1," on board",IDs[i+1],": SSS =",secs[i+1],"\nevent",i+2," on board",IDs[i+2],": SSS =",secs[i+2])

  # Check for time jumps in the past
  for uid in units:
      tdif = np.diff(secs[IDs==uid])
      aid = np.argwhere(tdif<0)
      for i in aid:
        #print(ind)
        #i = ind[1]
        #print(i,j,aid[j],xx)
        print("***Warning! Jump in past for unit",uid,"from SSS =",secs[IDs==uid][i],"to SSS =",secs[IDs==uid][i+1])
	
  # Plot a few graphs to check run quality
  if DISPLAY:
    pl.figure(1)
    pl.subplot(211)
    for uid in units:
      pl.plot(nsecs[IDs==uid],label=uid)
    pl.xlabel('Event nb')
    pl.ylabel('Nanosec counter value')
    pl.legend(loc='best')
    pl.subplot(212)
    for uid in units:
      pl.hist(nsecs[IDs==uid],100,label=uid)
    pl.xlabel('Nanosec counter value')
    pl.xlim([0,1e9])
    pl.legend(loc='best')

    pl.figure(2)
    for uid in units:
      pl.plot(ttimes[IDs==uid],label=uid)
    pl.xlabel('Event nb')
    pl.ylabel('Trigger time (s)')
    pl.legend(loc='best')
    pl.title('Event rate')
    
    pl.figure(3)
    pl.hist(IDs,100)
    pl.xlabel("Unit ID")
    pl.ylabel("Nb of events")
    
    pl.show()
    
    dur = max(ttimes)
    print(nevts,"events in run",nrun)
    print("Run duration:",dur,"seconds.")
    print("Units present in run:")
    for uid in units:
      print("Unit",uid,":",np.shape(np.where(IDs==uid))[1],"events.")
    input()

  # Format: ID sec nsec (ordered by increasing time)
  return res


def display_events(nrun=None,pyf=None,tid=None):
# Display timetraces
  print("Displaying timetraces for unit",tid)
  lab = ['X','Y','Z','Cal']
  if pyf == None:
    print("No pyef object, loading it from run number.")
    if nrun == None:
      print("get_time error! Pass run number or pyef object as argument")
      return  
    pyf = load_data(nrun)
  
  nevts = len(pyf.event_list)
  #print(nevts,"events in file",datafile)
  # TBD: access file header
  for evt in f.event_list:
  # Loop on all events
    #print("\n\n!!!New event!!!")
    for ls in evt.local_station_list:
    # Loop on all units involved in event (should be one only at this stage)
      uid = ls.header.ls_id - 356 # Remove 255 for digits 8-16 in IP adress & 100 for unit ID
      if tid==None or uid == tid:  
      # Display 
        raw = ls.adc_buffer
        hraw = [hex(int(a)) for a in raw]  # Transfer back to hexadecimal
        draw = [twos_comp(int(a,16), 12) for a in hraw] #2s complements
        draw = np.array(draw)*1./2048  # in Volts
        nsamples = int(ls.header.trace_length/4)  # draw corresponds to 4 channels
        #offset = int(nsamples/2.0)  # Offset position at center of waveform
        #print nsamples,"samples per channel --> offset = ",offset
        thisEvent = np.reshape(draw,(4,nsamples));
        thisEvent = pow(10,(thisEvent+np.min(thisEvent)))
        tmus = np.array(range(nsamples))*20e-3  # Time axis in mus
        evtnb = ls.header.event_nr
        pl.figure(1)
        for i in range(3):
          pl.plot(tmus[3:],thisEvent[i][3:],label=lab[i])
        pl.plot([tmus[int(nsamples/2)+15], tmus[int(nsamples/2)+15]],[np.min(thisEvent[:][:]),np.max(thisEvent[:][:])])
        pl.title('Evt {0} Antenna {1}'.format(evtnb,uid))
        pl.xlim(tmus[3],max(tmus))
        pl.xlabel('Time ($\mu$s)')
        pl.ylabel('Voltage (V)')
        pl.legend(loc="best")
        pl.show()
        input()
        pl.close(1)
	
	
def load_data(nrun):
# Loads pyef object
  datafile = datafolder+"/R"+nrun+".data.bin"
  if os.path.isfile(datafile) is False:
     print('File ',datafile,'does not exist. Aborting.')
     return

  print("Loading",datafile,"...")
  pyf = pyef.read_file(datafile)  #TBD: add error message if fails.
  print("Done.")
  return pyf


if __name__ == '__main__':
     if len(sys.argv)<2:
       print("Usage: >readData RUNID [BOARDID]")
     else: 
       # First load data
       f = load_data(sys.argv[1])
       if f == None:
         sys.exit()
	 
       # Display events
       display_events(pyf = f,tid=int(sys.argv[2]))
       
       # Perform recons
       loadMaxCoarse(sys.argv[1])
       uid,distmat = build_distmat()
       #print(uid,distmat)
       #input()
       trigtable = get_time(pyf=f)  # 2-lines matrix with [0,:]=UnitIDs and [1,:]=trigtimes
       build_coincs(trigtable,uid,distmat)
