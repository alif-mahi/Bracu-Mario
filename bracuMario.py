import sys
import random
import time
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

HIEGHT, WIDTH = 600, 800  

def display():
    glClear(GL_COLOR_BUFFER_BIT)
    glutSwapBuffers()

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RBG)
    glutInitWindowSize(WIDTH, HEIGHT)
    glutCreateWindow(b"Bracu Mario")
    glutOrtho2D(0, WIDTH, 0, HEIGHT)
    glClearColor(0, 0, 0, 0)
    glPointSize(2)

    glutDisplayFunc(display)
    glutMainLoop()

if __name__ == "__main__":
    main()
