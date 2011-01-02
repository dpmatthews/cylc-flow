#!/usr/bin/env python

# Cylc suite-specific configuration data. The awesome ConfigObj and
# Validate modules do almost everything we need. This just adds a 
# method to check the few things that can't be automatically validated
# according to the spec, $CYLC_DIR/conf/suite-config.spec, such as
# cross-checking some items.

import taskdef
import re, os, sys
from validate import Validator
from configobj import ConfigObj

# NOTE: DUMMY MODIFIER NOT NEEDED: JUST OMIT COMMAND LIST IN SUITE.RC

class SuiteConfigError( Exception ):
    """
    Attributes:
        message - what the problem is. 
        TO DO: element - config element causing the problem
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)


class config( ConfigObj ):
    allowed_modifiers = ['dummy', 'contact', 'oneoff', 'sequential', 'catchup', 'catchup_contact']

    def __init__( self, file=None, spec=None ):
        if file:
            self.file = file
        else:
            self.file = os.path.join( os.environ[ 'CYLC_SUITE_DIR' ], 'suite.rc' ),

        if spec:
            self.spec = spec
        else:
            self.spec = os.path.join( os.environ[ 'CYLC_DIR' ], 'conf', 'suite-config.spec')

        # load config
        ConfigObj.__init__( self, self.file, configspec=self.spec )

        # validate and convert to correct types
        val = Validator()
        test = self.validate( val )
        if test != True:
            # TO DO: elucidate which items failed
            # (easy - see ConfigObj and Validate documentation)
            print test
            raise SuiteConfigError, "Suite Config Validation Failed"
        
        # check cylc-specific self consistency
        self.__check()

    def __check( self ):
        #for task in self['tasks']:
        #    # check for illegal type modifiers
        #    for modifier in self['tasks'][task]['type modifier list']:
        #        if modifier not in self.__class__.allowed_modifiers:
        #            raise SuiteConfigError, 'illegal type modifier for ' + task + ': ' + modifier

        # check families do not define commands, etc.
        pass

    def get_task_name_list( self ):
        return self['tasks'].keys()

    def get_task_shortname_list( self ):
        return self['tasks'].keys()

    def generate_task_classes( self, dir ):
        taskdefs = {}

        for cycle_list in self['dependency graph']:
            cycles = re.split( '\s*,\s*', cycle_list )

            for label in self['dependency graph'][ cycle_list ]:
                line = self['dependency graph'][cycle_list][label]

                sequence = re.split( '\s*->\s*', line )
                count = 0
                tasks = {}

                for name in sequence:
                    specific_output = False
                    m = re.match( '(\w+)\((\d+)\)', name )
                    if m:
                        specific_output = True
                        name = m.groups()[0]
                        output_n = m.groups()[1]

                    if name not in taskdefs:
                        # first time seen; define everything except for
                        # possible additional prerequisites.
                        if name not in self['tasks']:
                            raise SuiteConfigError, 'task ' + name + ' not defined'
                        taskconfig = self['tasks'][name]
                        taskd = taskdef.taskdef( name )

                        for item in taskconfig[ 'type list' ]:
                            if item == 'coldstart':
                                taskd.modifiers.append( 'oneoff' )
                                taskd.coldstart = True
                                continue
                            if item == 'free':
                                taskd.type = 'free'
                                continue
                            if item == 'oneoff' or \
                                item == 'sequential' or \
                                item == 'catchup':
                                taskd.modifiers.append( item )
                                continue
                            
                            m = re.match( 'model\(\s*restarts\s*=\s*(\d+)\s*\)', item )
                            if m:
                                taskd.type = 'tied'
                                taskd.n_restart_outputs = m.groups()[0]
                                continue

                            m = re.match( 'clock\(\s*offset\s*=\s*(\d+)\s*hour\s*\)', item )
                            if m:
                                taskd.modifiers.append( 'contact' )
                                taskd.contact_offset = m.groups()[0]
                                continue

                            m = re.match( 'catchup clock\(\s*offset\s*=\s*(\d+)\s*hour\s*\)', item )
                            if m:
                                taskd.modifiers.append( 'catchup_contact' )
                                taskd.contact_offset = m.groups()[0]
                                continue

                            raise SuiteConfigError, 'illegal task type: ' + item

                        taskd.logfiles = []
                        taskd.commands = taskconfig[ 'command list' ]
                        taskd.environment = taskconfig[ 'environment' ]
                        #taskd.directives = taskconfig[ 'directives' ]
                        #taskd.scripting = taskconfig[ 'scripting' ]

                        taskdefs[ name ] = taskd

                    for hour in cycles:
                        if hour not in taskdefs[name].hours:
                            taskdefs[name].hours.append( hour )

                    if count > 0:
                        if taskdefs[prev_name].coldstart:
                            if cycle_list not in taskdefs[prev_name].outputs:
                                taskdefs[prev_name].outputs[cycle_list] = []
                            taskdefs[prev_name].outputs[ cycle_list ].append( "'" + name + " restart files ready for ' + self.c_time" )
                        else:
                            if cycle_list not in taskdefs[name].prerequisites:
                                taskdefs[name].prerequisites[cycle_list] = []
                            if prev_specific_output:
                                # trigger off specific output of previous task
                                if cycle_list not in taskdefs[prev_name].outputs:
                                    taskdefs[prev_name].outputs[cycle_list] = []
                                specout = self['tasks'][prev_name]['outputs'][output_n]

                                # replace $(CYCLE_TIME +/- N)
                                m = re.search( '\$\(\s*CYCLE_TIME\s*\+\s*(\d+)\s*\)', specout )
                                if m:
                                    specout = re.sub( '\$\(\s*CYCLE_TIME.*\)', '" + cycle_time.increment( self.c_time )+ "', specout )
                                m = re.search( '\$\(\s*CYCLE_TIME\s*\-\s*(\d+)\s*\)', specout )
                                if m:
                                    specout = re.sub( '\$\(\s*CYCLE_TIME.*\)', '" + cycle_time.decrement( self.c_time )+ "', specout )
                                specout = re.sub( '\$\(\s*CYCLE_TIME\s*\)', '" + self.c_time + "', specout )

                                taskdefs[prev_name].outputs[  cycle_list ].append( '"' + specout + '"')
                                taskdefs[name].prerequisites[ cycle_list ].append( '"' + specout + '"')
                            else:
                                # trigger off previous task finished
                                taskdefs[name].prerequisites[ cycle_list ].append( "'" + prev_name + "%' + self.c_time + ' finished'" )
                    count += 1
                    prev_name = name
                    prev_specific_output = specific_output

        members = []
        my_family = {}
        for name in self['families']:
            taskdefs[name].type="family"
            mems = self['families'][name]
            taskdefs[name].members = mems
            for mem in mems:
                if mem not in members:
                    members.append( mem )
                    taskd = taskdef.taskdef( mem )
                    taskd.member_of = name
                    # take valid hours for family members 
                    # from the family
                    taskd.hours = taskdefs[name].hours
                    taskd.logfiles = []
                    taskconfig = self['tasks'][mem]
                    taskd.commands = taskconfig[ 'command list' ]
                    taskd.environment = taskconfig[ 'environment'  ]
                    #taskd.directives = taskconfig[ 'directives'   ]
                    #taskd.scripting = taskconfig[ 'scripting'    ]

                    taskdefs[ mem ] = taskd

        for name in taskdefs:
            taskdefs[name].hours.sort( key=int ) 
            print name, taskdefs[name].type, taskdefs[name].hours, taskdefs[name].commands
            taskdefs[name].write_task_class( dir )

