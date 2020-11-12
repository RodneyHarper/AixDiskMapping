#!/usr/bin/python
import os
import sys
import re
from pprint import pprint

username="root"
hostname=sys.argv[1]
system={}

############################################################
def getLparInfo():
    (system['lpar_id'],system['lpar_name']) = ssh('uname -L').read().split()
    system['chassis'] = system['lpar_name'].split('-')[0]
    tmp={
        'lpar_id':system['lpar_id'],
        'chassis':system['chassis'],
        'lpar_name':system['lpar_name'],
        }
    return tmp

############################################################
def getHMCinfo(lparinfo):
    tmp=[]
    cmd='lshwres -r virtualio --rsubtype scsi -m %s --filter lpar_ids=%s' % ( lparinfo['chassis'], lparinfo['lpar_id'] )
    for hmc_line in ssh(cmd, username='hscroot', host="%s-mgt" % lparinfo['chassis']):
        hmc_line = hmc_line.strip()
        if not hmc_line:
            continue
        hmc={}
        hmc['lpar'] = lparinfo # ref to lpar array
        for kv in hmc_line.split(','):
            (k,v) = kv.split('=')
            hmc[k] = v
        tmp.append(hmc)
    return tmp

############################################################
def ssh(cmd, username='root', host=None):
    if not host:
        host=hostname
    f=os.popen("sudo ssh %s@%s '%s'" % (username, host, cmd))
    return f
    
############################################################
def getPhysVol(lpar):
    tmp=[]
    for lspv_line in ssh('lspv').readlines():
        lspv = lspv_line.split()
        pv={}
        pv['lpar'] = lpar # ref to lpar array
        pv['pv_name'] = lspv[0]
        pv['pv_id'] = lspv[1]
        pv['vg_name'] = lspv[2]
        pv['pv_status'] = lspv[3]
        tmp.append(pv)
    return tmp

############################################################
def getLparVscsi(physvol):
    tmp=[]
    cmd='lspath -l %s -F"parent"' % ( physvol['pv_name'] )
    for vscsi_line in ssh(cmd):
        vscsi_line = vscsi_line.strip()
        if not vscsi_line:
                continue
        vscsi={}
        vscsi['pv'] = physvol # ref to pv array
        vscsi['vscsi_id'] = vscsi_line
        tmp.append(vscsi)
    return tmp

############################################################
def getVscsiDetail(lparvscsi):
    tmp=[]
    cmd='lscfg -l %s' % ( lparvscsi['vscsi_id'] )
    for vscsi_line in ssh(cmd):
        vscsidetail_line = vscsidetail_line.strip()
        if not vscsidetail_line:
            continue
        vscsidetail={}
        vscsidetail['vscsi'] = lparvscsi # ref to vsci array
        vscsidetail_line = vscsidetail_line.split()
        vscsidetail['vscsi_physical'] = vscsidetail_line[1]
        vscsidetail['vscsi_slot_num'] = vscsidetail['vscsi_physical'].split("-")[2].replace('C','')
        vscsidetail['description'] = vscsidetail_line[2:]
        tmp.append(vscsidetail)
    return tmp

############################################################
def getMultipathing():
    system['lspath'] = []
    for pv in system['pv']:
	#print pv['pv_name']
	cmd='lspath -l %s -F"connection parent path_status status"' % pv['pv_name']
	CmdString = "sudo ssh %s@%s '%s'" % (username, hostname, cmd)
	for lspath_line in os.popen(CmdString).readlines():
		lspath_line = lspath_line.strip()
		if not lspath_line:
			continue
		lspath_line = lspath_line.split()
		lspath={}
		lspath['pv'] = pv # ref to pv array
		lspath['pv_name'] = pv['pv_name'] 
		lspath['connection'] = lspath_line[0]
		lspath['vscsi_id'] = lspath_line[1]
		lspath['path_status'] = lspath_line[2]
		lspath['status'] = lspath_line[3]
                system['lspath'].append(lspath)
		for vscsi in system['vscsi']:
			if vscsi['vscsi_id'] == lspath['vscsi_id']:
				vscsi['lspath'] = lspath
#print "system lspath:"
#print system['lspath']
# output
# 810000000000 vscsi0 Available Enabled
# 810000000000 vscsi1 Available Enabled
# 810000000000 vscsi3 Missing   N/A
# 810000000000 vscsi2 Missing   N/A
# 820000000000 vscsi3 Available Enabled
############################################################
def getVHadaptor():
    system['vh'] = []
    for hmc in system['hmc']: #RH  --- works
	#print hmc['remote_slot_num']
	cmd='/usr/ios/cli/ioscli lsdev -vpd | grep vhost | grep C%s' % hmc['remote_slot_num'] 
	CmdString = "sudo ssh %s@%s '%s'" % (username, hmc['remote_lpar_name'], cmd)
	for vh_line in os.popen(CmdString).readlines():
		vh_line = vh_line.strip()
		if not vh_line:
			continue
		vh_line = vh_line.split()
		vh={}
		vh['vhost'] = vh_line[0]
		vh['vscsi_physical'] = vh_line[1]
		vh['remote_slot_num'] = vh['vscsi_physical'].split("-")[2].replace('C','')
		vh['description'] = vh_line[2:]
		vh['hmc'] = hmc
		system['vh'].append(vh)
	#	for hmc in system['hmc']: 
	#		if hmc['remote_slot_num'] == vh['remote_slot_num']: 
	#			hmc['vh'] = vh 
	#	for vscsi in system['vscsi']: 
	#		if vscsi['hmc']['remote_slot_num'] == vh['remote_slot_num']: 
	#			vscsi['vh'] = vh 
#print "system vh:"
#print system['vh']
# output
#  vhost29          U9117.MMA.063F470-V2-C42                                      Virtual SCSI Server Adapter
#  vhost29          U9117.MMA.063F470-V3-C42                                      Virtual SCSI Server Adapter
#  vhost13          U9117.MMA.063F470-V2-C26                                      Virtual SCSI Server Adapter
#  vhost13          U9117.MMA.063F470-V3-C26                                      Virtual SCSI Server Adapter
############################################################
def getBackingDevs():
    system['backing_devs'] = []
    for vh in system['vh']:
	vh['backing'] = [] 
	vh['backing_device'] = [] 
	cmd='/usr/ios/cli/ioscli lsmap -vadapter %s' % vh['vhost']
	CmdString = "sudo ssh %s@%s '%s'" % (username, vh['hmc']['remote_lpar_name'], cmd)
	backing={} 
	backing['backing_device'] = []
	backing['remote_lpar_name'] = []
	for backing_line in os.popen(CmdString).readlines():
		backing_line = backing_line.strip()
		if not backing_line:
			continue
		if " hdisk" in backing_line: 
			backing['remote_lpar_name'] = vh['hmc']['remote_lpar_name']
			backing_line = backing_line.split() 
			vh['backing_device'].append(backing_line[2]) 
			print vh['backing_device']
			check=len(vh['backing_device'])  # returns count of backing devices
			if check > 1:
				print "check: %s is greater than 1" % check
				#backing['backing_device'] =  vh['backing_device']
				#print backing['backing_device']
				#backing['backing_device'] = vh['backing_device'][2]
				#system['backing_devs'].append(backing) 
				#backing.pop('backing_device')
				#del system['backing_devs'][-1]
				backing['backing_device'] = backing_line[2]
				#system['backing_devs'].insert(0,backing) 
				#system['backing_devs'].pop(-1) 
				system['backing_devs'].append(backing) 
				#system['backing_devs'].pop(-1) 
				#system['backing_devs'].append(backing) 
				print "backing device: %s" % backing['backing_device']
			else:
				print "check: %s is not greater than 1" % check
				backing['backing_device'] = backing_line[2]
				system['backing_devs'].append(backing) 
				print "backing device: %s vh backing device: %s lpar: %s" % (backing['backing_device'], vh['backing_device'], vh['hmc']['remote_lpar_name'])
				continue
			#if backing['backing_device'].count(7):
				#system['backing_device'].pop(-1)
				#print backing['backing_device']
				#print "system['backing_device'].pop(-1)"
			#else:
			#	continue
			#print backing['backing_device'].count('backing_device')
			#print "lpar: %s (backing) backing device: %s vh backing device: %s" % (vh['hmc']['remote_lpar_name'], backing['backing_device'], vh['backing_device'])    # backing['backing_device'] is correct
#	pattern = re.compile('&(?!#)(?!amp;)(?!quot;)(?!lt;)(?!gt;)')
#	pattern = " hdisk"
#	for i, line in enumerate(backing_lines):
#		if pattern.search(line):
#			print i, line

    print "system backing_devs:"
    print system['backing_devs']
    sys.exit()
#for vh in system['vh']:
#	for backing in system['backing_devs']:
#		print "vhost: %s backing device: %s " % ( vh['vhost'], backing['backing_device'] )
# output
# Backing device        hdisk16 a
# Backing device        hdisk16 b
# Backing device        hdisk26 b
# Backing device        hdisk47 a
# Backing device        hdisk47 b
############################################################
def getLUNdetails():
    system['lun'] = []
    for backing in system['backing_devs']:
	vh['lun'] = []
	cmd='/usr/ios/cli/ioscli lsdev -dev %s' % backing['backing_device']
	CmdString = "sudo ssh %s@%s '%s -attr'" % (username, vh['hmc']['remote_lpar_name'], cmd)
	lun={}
	for lun_line in os.popen(CmdString).readlines():
		lun_line = lun_line.strip().split()
		if not lun_line:
			continue
		k = lun_line[0]
		v = lun_line[1]
		lun[k] = v
		lun['pv'] = pv # ref to pv array
		system['lun'].append(lun)
    print "system lun:"
    print system['lun']
# output
# lun_id         0x8000000000000
# reserve_policy no_reserve
# ww_name        0x50060e800457b838
# lun_id         0x8000000000000
# reserve_policy no_reserve
# ww_name        0x50060e800457b828
# lun_id         0x8000000000000
# reserve_policy PR_exclusive
# ww_name        0x50060e800457b828
# lun_id         0x27000000000000
# reserve_policy no_reserve
# ww_name        0x50060e800457b838
# lun_id         0x27000000000000
# reserve_policy no_reserve
# ww_name        0x50060e800457b828
############################################################
def getLdevDetails():
    system['ldev'] = []
    cmd='odmget -qattribute=unique_id CuAt' 
    CmdString = "sudo ssh %s@%s-vioa '%s'" % (username, system['chassis'], cmd) # test against A for now
    for odm_line in os.popen(CmdString).readlines():
	odm_line = odm_line.strip()
	if "CuAt:" in odm_line:
		continue 
	odm_line = odm_line.split()
	odm={}
	odm['name'] = odm_line[0]
	odm['attribute'] = odm_line[1]
	odm['value'] = odm_line[2]
	odm['type'] = odm_line[3]
	odm['generic'] = odm_line[4]
	odm['rep'] = odm_line[5]
	odm['nls_index'] = odm_line[6]
	system['ldev'].append(ldev)
	if not odm_line:
		continue
    print "system ldev:"
    print system['ldev']
# output
#pprint(system)
#CuAt:
#        name = "hdisk0"
#        attribute = "unique_id"
#        value = "21080002FB130AST373455LC03IBMscsi"
#        type = "R"
#        generic = ""
#        rep = "nl"
#        nls_index = 79
#
#CuAt:
#        name = "hdisk1"
#        attribute = "unique_id"
#        value = "21080002F94A0AST373455LC03IBMscsi"
#        type = "R"
#        generic = ""
#        rep = "nl"
#        nls_index = 79
############################################################
def Report():
    print "-"*80
    print "LPAR - DISK TO SAN MAP"
    print "-"*80
    print "System Name: %s\nSystem ID: %s\nChassis: %s " % ( system['lpar_name'],system['lpar_id'], system['chassis'] )
    print "-"*80
    print "-"*80
    print "vg ->\tpv (state) ->\tlpar vscsi (path status) -> \tslot number ->\tremote vio ->\tremote slot number ->\tvio vscsi ->\tbacking device ->\tlun id ->\tww_name ->\treserve policy ->\tldev ->:\n"
    for vscsi in system['vscsi']:
            print "%s ->\t%s (%s) ->\t%s (%s) ->\t%s ->\t%s ->\t%s ->\t%s ->\t%s ->\t%s ->\t%s ->" % ( vscsi['pv']['vg_name'], vscsi['pv']['pv_name'], vscsi['pv']['pv_status'], vscsi['lspath']['vscsi_id'], vscsi['lspath']['path_status'].lower(), vscsi['vscsi_slot_num'], vscsi['hmc']['remote_lpar_name'], vscsi['hmc']['remote_slot_num'], vscsi['vh']['vhost'], vscsi['vh']['backing_device'], lun['lun_id'], lun['reserve_policy'] )
    print "-"*80
    print "-"*80
    print "multipathing:\nPhysical Volume\t(state)\tconnection\tadapter\t\tpath status\tstate"
    print "-"*80
    for vscsi in system['vscsi']:
                    print "%s\t\t%s\t%s\t%s\t\t%s\t%s" % (  vscsi['pv']['pv_name'], vscsi['pv']['pv_status'], vscsi['lspath']['connection'], vscsi['lspath']['vscsi_id'], vscsi['lspath']['path_status'], vscsi['lspath']['status'] )

system['lpar']=getLparInfo()
system['hmc']=getHMCinfo(system['lpar'])
system['pv']=getPhysVol(system['lpar'])
system['vscsi']=getLparVscsi(system['pv'])
system['vscsidetail']=getVscsiDetail(system['vscsi'])
#getMultipathing()
#getVHadaptor()
#getBackingDevs()
#getLUNdetails()
#getLdevDetails()
#Report()
