''''
NOT USED... ABSTRACTED AWAY TO DICTIONARY
''''

import math


class VectorClocks:

    def __init__(self, viewList):

        self.VC = {}

        for x in range(len(viewList)):
            self.VC.update({str(viewList[x]): 0})

    def constHash(self, val):

        

        return math.sin(val)



    def returnVC(self):

        return self.VC

    def updateVC(self, addr, vcvalue):

        self.VC.update({str(addr): vcvalue})
    
    def updateVCDelivery(self, vc):

        for x in self.VC:
            if(self.VC[x] < vc[x]):
                self.VC.update({x:vc[x]})
        return 0
    
    def replaceVC(self, VC):

        self.VC.clear()
        self.VC.update(VC)

    #def VcComparator(self, VC1, VC2):
    #    array = []
    #    for x in VC1:
    #        if(VC1[x] == VC2[x]):
    #            array.append("e")
    #        if(VC1[x] < VC2[x]):
    #            array.append("l")
    #        if(VC1[x] > VC2[x]):
    #            array.append("g")

    #    if( ("e" in array) and ("l" not in array) and ("g" not in array) ):
    #        return "="
    #    if( ("l" in array) and ("e" not in array) and ("g" not in array) ):
    #        return "<"
    #    if( ("e" in array) and ("l" in array) and ("g" not in array) ):
    #        return "<"
    #    if( ("g" in array) and ("e" not in array) and ("l" not in array) ):
    #        return ">"
    #    if( ("g" in array) and ("e" in array) and ("l" not in array) ):
    #        return ">"
    #    if( ("g" in array) and ("l" in array) ):
    #        return "||"

    def VcComparator(self, VC1, VC2):

        #compares VC1 to VC2; 
        # if VC1 is greater than VC2, return ">"
        # if VC1 is less than VC2, return "<"
        # if VC1 is concurrent with VC2, return "||"
        # if VC1 is equal to VC2, return "="

        vc1Bool = False
        vc2Bool = False

        for x in VC1:

            if(VC1[x] < VC2[x]):
                vc2Bool = True
            
            if(VC1[x] > VC2[x]):
                vc1Bool = True

        if(vc1Bool == True and vc2Bool == False):
            return ">"

        if(vc2Bool == True and vc1Bool == False):
            return "<"
        
        if(vc1Bool == True and vc2Bool == True):
            return "||"
        
        if(vc1Bool == False and vc2Bool == False):
            return "="