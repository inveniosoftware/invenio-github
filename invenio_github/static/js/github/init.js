/*
 * This file is part of Invenio.
 * Copyright (C) 2014, 2015, 2016 CERN.
 *
 * Invenio is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Invenio is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Invenio. If not, see <http://www.gnu.org/licenses/>.
 *
 * In applying this licence, CERN does not waive the privileges and immunities
 * granted to it by virtue of its status as an Intergovernmental Organization
 * or submit itself to any jurisdiction.
 */

require([
  'jquery',
  'node_modules/bootstrap-switch/dist/js/bootstrap-switch',
  'js/github/view'
  ], function() {
    /*
     * It preloads js/github/view to give it a name so you're free to use it
     * from any places.
     */
    console.info("js/github/init is loaded");
});
