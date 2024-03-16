.pragma library

function vecMake(n, val)
{
  let result = [];
  for (let i = 0; i < n; ++i) {
    result[i] = val;
  }
  return result;
}

function matMake(rows, cols, val)
{
  let result = [];
  for (let i = 0; i < rows; ++i) {
    result[i] = [];
    for (let j = 0; j < cols; ++j) {
      result[i][j] = val;
    }
  }
  return result;
}

function matProduct(ma, mb)
{
  let aRows = ma.length;
  let aCols = ma[0].length;
  let bRows = mb.length;
  let bCols = mb[0].length;
  if (aCols != bRows) {
    throw "Non-conformable matrices";
  }

  let result = matMake(aRows, bCols, 0.0);

  for (let i = 0; i < aRows; ++i) { // each row of A
    for (let j = 0; j < bCols; ++j) { // each col of B
      for (let k = 0; k < aCols; ++k) { // could use bRows
        result[i][j] += ma[i][k] * mb[k][j];
      }
    }
  }

  return result;
}

function matInverse(m)
{
  // assumes determinant is not 0
  // that is, the matrix does have an inverse
  let n = m.length;
  let result = matMake(n, n, 0.0); // make a copy
  for (let i = 0; i < n; ++i) {
    for (let j = 0; j < n; ++j) {
      result[i][j] = m[i][j];
    }
  }

  let lum = matMake(n, n, 0.0); // combined lower & upper
  let perm = vecMake(n, 0.0);  // out parameter
  matDecompose(m, lum, perm);  // ignore return

  let b = vecMake(n, 0.0);
  for (let i = 0; i < n; ++i) {
    for (let j = 0; j < n; ++j) {
      if (i == perm[j])
        b[j] = 1.0;
      else
        b[j] = 0.0;
    }

    let x = reduce(lum, b); // 
    for (let j = 0; j < n; ++j)
      result[j][i] = x[j];
  }
  return result;
}

function matDeterminant(m)
{
  let n = m.length;
  let lum = matMake(n, n, 0.0);;
  let perm = vecMake(n, 0.0);
  let result = matDecompose(m, lum, perm);  // -1 or +1
  for (let i = 0; i < n; ++i)
    result *= lum[i][i];
  return result;
}

function matDecompose(m, lum, perm)
{
  // Crout's LU decomposition for matrix determinant and inverse
  // stores combined lower & upper in lum[][]
  // stores row permuations into perm[]
  // returns +1 or -1 according to even or odd perms
  // lower gets dummy 1.0s on diagonal (0.0s above)
  // upper gets lum values on diagonal (0.0s below)

  let toggle = +1; // even (+1) or odd (-1) row permutatuions
  let n = m.length;

  // make a copy of m[][] into result lum[][]
  //lum = matMake(n, n, 0.0);
  for (let i = 0; i < n; ++i) {
    for (let j = 0; j < n; ++j) {
      lum[i][j] = m[i][j];
    }
  }

  // make perm[]
  //perm = vecMake(n, 0.0);
  for (let i = 0; i < n; ++i)
    perm[i] = i;

  for (let j = 0; j < n - 1; ++j) {  // note n-1 
    let max = Math.abs(lum[j][j]);
    let piv = j;

    for (let i = j + 1; i < n; ++i) {  // pivot index
      let xij = Math.abs(lum[i][j]);
      if (xij > max) {
        max = xij;
        piv = i;
      }
    } // i

    if (piv != j) {
      let tmp = lum[piv];  // swap rows j, piv
      lum[piv] = lum[j];
      lum[j] = tmp;

      let t = perm[piv];  // swap perm elements
      perm[piv] = perm[j];
      perm[j] = t;

      toggle = -toggle;
    }

    let xjj = lum[j][j];
    if (xjj != 0.0) {  // TODO: fix bad compare here
      for (let i = j + 1; i < n; ++i) {
        let xij = lum[i][j] / xjj;
        lum[i][j] = xij;
        for (let k = j + 1; k < n; ++k) {
          lum[i][k] -= xij * lum[j][k];
        }
      }
    }

  } // j

  return toggle;  // for determinant
} // matDecompose

function reduce(lum, b) // helper
{
  let n = lum.length;
  let x = vecMake(n, 0.0);
  for (let i = 0; i < n; ++i) {
    x[i] = b[i];
  }

  for (let i = 1; i < n; ++i) {
    let sum = x[i];
    for (let j = 0; j < i; ++j) {
      sum -= lum[i][j] * x[j];
    }
    x[i] = sum;
  }

  x[n - 1] /= lum[n - 1][n - 1];
  for (let i = n - 2; i >= 0; --i) {
    let sum = x[i];
    for (let j = i + 1; j < n; ++j) {
      sum -= lum[i][j] * x[j];
    }
    x[i] = sum / lum[i][i];
  }

  return x;
} // reduce

function matTranspose(m1) {
  let m2 = [];
  for (let i = 0; i < m1[0].length; i++) {
    m2.push([]);
  }
  for (let r in m1) {
    for (let i = 0; i < m1[r].length; i++) {
      m2[i].push(m1[r][i]);
    }
  }
  return m2;
}

function bedMetrics(mesh) {
    /* convert the mesh into an xy1 matrix and a z matrix, such that:
     * xy1 = [[ x0   x1   x2   x3 ... ]
     *        [ y0   y1   y2   y3 ... ]
     *        [ 1    1    1    1  ... ]]
     * z   = [[ z0   z1   z2   z3 ... ]]
     */
    var bedxy1 = [[], [], []];
    var bedz = [[]];
    var zmin = 0;
    var zmax = 0;
    for (var y in mesh) {
        for (var x in mesh[y]) {
            bedxy1[0].push(parseFloat(y));
            bedxy1[1].push(parseFloat(x));
            bedxy1[2].push(1);
            var z = parseFloat(mesh[y][x]);
            bedz[0].push(z);
            zmin = Math.min(zmin, z);
            zmax = Math.max(zmax, z);
        }
    }
	
    /* matrix algebra least squares regression
     * (https://online.stat.psu.edu/stat462/node/132/)
     *
     * z * xy1.T * ((xy1 * xy1.T) ^ -1)
     */
    var K0s = matProduct(matProduct(bedz, matTranspose(bedxy1)),
                         matInverse(matProduct(bedxy1, matTranspose(bedxy1))));
    var tiltx = Math.abs(K0s[0][1] * 256);
    var tilty = Math.abs(K0s[0][0] * 256);
  
    /* compute a mesh with our proposed correction applied, and compute the maximum deviation with that */	
    var z2min = 0;
    var z2max = 0;
    for (let y in mesh) {
        for (let x in mesh[y]) {
            let newz = mesh[y][x] - K0s[0][0] * parseFloat(y) - K0s[0][1] * parseFloat(x) - K0s[0][2];
            z2min = Math.min(z2min, newz);
            z2max = Math.max(z2max, newz);
        }
    }
    return { tiltX: tiltx, tiltY: tilty, nonplanarity: z2max - z2min, peakToPeak: zmax - zmin };
}

function describeMetrics(metrics) {
    let description = "";
    if (Math.sqrt(metrics.tiltX * metrics.tiltX + metrics.tiltY * metrics.tiltY) > 0.3) {
        description = qsTr("Your hotbed appears not to be level. Try tramming the bed.");
    } else if (metrics.nonplanarity > 1.0) {
        description = qsTr("Your hotbed appears reasonably level, but may be warped.");
    } else {
        description = qsTr("Your hotbed appears to be flat and level.");
    }
    console.log(`[x1p] MeshCalcs: description for ${metrics.tiltX} tiltX, ${metrics.tiltY} tiltY, ${metrics.nonplanarity} nonplanarity is ${description}`);
    return description;
}
