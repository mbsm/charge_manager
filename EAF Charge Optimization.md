EAF Charge Optimization 


The problem of optimal charge is described here. 

a) raw materiasl
Denoted as M_i there are n row materials each one has a cost Ci. the chemestry of the material is defined by two vectors MQmin_i and MQmax_i. this vectors has m components each one correspond to a chemestry element.

b) desition variables
Denoted as x_i correspond to the mass of the raw material -i to be cosidered for the charge.

c) Restrictions
    i) the chemestry of the charge resulting from raw material mix needs to be in a range defined by two m-dimensional vetors HQmin , HQmax. For this bought the min chemestry and max chemestry needs to be in this range
    ii) the total weight of the charge need to equal the requiered weigth, ie sum(x_i)== Heat_weight
    iii) the percentage of each raw material in the mix needs to be in a limit: MPmin_i  < x_i/sum(x_j) < MPmax_i

d) objective finction: minimize the cost of the charge: sum(x_i*c_i)


